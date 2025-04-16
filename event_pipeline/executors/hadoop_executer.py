import typing
import logging
import time
import threading
from concurrent.futures import Executor, Future
from concurrent.futures._base import (
    PENDING,
    RUNNING,
    FINISHED,
    CANCELLED,
    CANCELLED_AND_NOTIFIED,
)
from event_pipeline.base import EventBase

logger = logging.getLogger(__name__)

# Import actual Hadoop client libraries
try:
    import pyarrow.hdfs as hdfs
    from pyhadoop import hadoop_client
    from pyhadoop.yarn import YarnClient
    from pyhadoop.mapreduce import JobClient
except ImportError:
    logger.warning(
        "Hadoop client libraries not found. "
        "Please install with: pip install pyarrow hadoop-python-client"
    )


class HadoopJobError(Exception):
    """Exception raised for errors in Hadoop job execution."""

    pass


class HadoopConnector:
    """Handles connection to Hadoop service using actual Hadoop client libraries."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str = None,
        password: str = None,
        kerb_ticket: str = None,
        hdfs_config: typing.Dict[str, str] = None,
        yarn_config: typing.Dict[str, str] = None,
    ):
        """
        Initialize the Hadoop connector.

        Args:
            host: Hadoop namenode hostname.
            port: Hadoop namenode port.
            username: Username for authentication.
            password: Password for authentication.
            kerb_ticket: Path to Kerberos ticket file for authentication (alternative to password).
            hdfs_config: Additional HDFS configuration parameters.
            yarn_config: Additional YARN configuration parameters.
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.kerb_ticket = kerb_ticket
        self.hdfs_config = hdfs_config or {}
        self.yarn_config = yarn_config or {}

        # Client connections
        self._hdfs_client = None
        self._yarn_client = None
        self._job_client = None

        # Connection settings
        self.connection_timeout = 30  # seconds
        self.connection_retries = 3

        # Job tracking
        self._job_results = {}  # Store job metadata by job_id

    def connect(self) -> bool:
        """
        Establish connection to Hadoop.
        Returns:
            bool: True if connection was successful, False otherwise.
        """
        # Check if dependencies are installed
        if not all(
            module in globals()
            for module in ["hdfs", "hadoop_client", "YarnClient", "JobClient"]
        ):
            raise ImportError(
                "Required Hadoop client libraries not found. "
                "Please install with: pip install pyarrow hadoop-python-client"
            )

        if self._hdfs_client is not None:
            # Already connected
            return True

        for attempt in range(self.connection_retries):
            try:
                logger.info(
                    f"Connecting to Hadoop at {self.host}:{self.port} (attempt {attempt + 1})"
                )

                # Connect to HDFS
                hdfs_extra_conf = {
                    "dfs.client.read.shortcircuit": "true",
                    "dfs.domain.socket.path": "/var/lib/hadoop-hdfs/dn_socket",
                }
                hdfs_extra_conf.update(self.hdfs_config)

                self._hdfs_client = hdfs.connect(
                    host=self.host,
                    port=self.port,
                    user=self.username,
                    kerb_ticket=(
                        self.kerb_ticket
                        if self.kerb_ticket
                        else "default" if not self.password else None
                    ),
                    extra_conf=hdfs_extra_conf,
                )

                # Connect to YARN for job submission and monitoring
                yarn_config = {
                    "yarn.resourcemanager.hostname": self.host,
                    "yarn.resourcemanager.address": f"{self.host}:8032",
                    "yarn.resourcemanager.scheduler.address": f"{self.host}:8030",
                }
                yarn_config.update(self.yarn_config)

                self._yarn_client = YarnClient(
                    hostname=self.host,
                    username=self.username,
                    password=self.password,
                    kerberos_ticket=self.kerb_ticket,
                    config=yarn_config,
                )

                # Initialize job client for MapReduce jobs
                self._job_client = JobClient(self._yarn_client)

                logger.info(
                    f"Successfully connected to Hadoop at {self.host}:{self.port}"
                )
                return True

            except Exception as e:
                logger.error(
                    f"Failed to connect to Hadoop (attempt {attempt + 1}): {str(e)}"
                )
                # Exponential backoff for retries
                time.sleep(min(2**attempt, 10))

        logger.error(
            f"Failed to connect to Hadoop after {self.connection_retries} attempts"
        )
        return False

    def disconnect(self) -> None:
        """Close Hadoop connection."""
        if self._hdfs_client:
            try:
                logger.info(f"Disconnecting from Hadoop at {self.host}:{self.port}")

                # Close HDFS connection
                self._hdfs_client.close()
                self._hdfs_client = None

                # Close YARN connection
                if self._yarn_client:
                    self._yarn_client.close()
                    self._yarn_client = None

                # Clear job client
                self._job_client = None

                logger.info(f"Successfully disconnected from Hadoop")
            except Exception as e:
                logger.error(f"Error disconnecting from Hadoop: {str(e)}")

    def _serialize_job(self, fn, args, kwargs) -> str:
        """
        Serialize a function and its arguments to be executed on Hadoop.
        Args:
            fn: The function to serialize.
        Returns:
            str: Path to the serialized job file in HDFS.
        """
        import pickle
        import tempfile
        import os
        from datetime import datetime

        # Create a temporary local file for the serialized job
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pkl") as temp_file:
            temp_path = temp_file.name
            pickle.dump((fn, args, kwargs), temp_file)

        try:
            # Upload to HDFS
            hdfs_job_dir = f"/tmp/hadoop_executor/{self.username}/jobs"
            if not self._hdfs_client.exists(hdfs_job_dir):
                self._hdfs_client.mkdir(hdfs_job_dir)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            job_name = getattr(fn, "__name__", "anonymous_task")
            hdfs_path = f"{hdfs_job_dir}/{job_name}_{timestamp}.pkl"

            with open(temp_path, "rb") as local_file:
                self._hdfs_client.upload(hdfs_path, local_file)

            return hdfs_path
        finally:
            # Clean up the local temporary file
            os.unlink(temp_path)

    def submit_job(self, job_config: dict) -> str:
        """
        Submit a job to Hadoop and return job ID.

        Args:
            job_config: Dictionary containing job configuration details.

        Returns:
            str: Job identifier.

        Raises:
            ConnectionError: If not connected to Hadoop.
        """
        if not self._hdfs_client or not self._yarn_client:
            if not self.connect():
                raise ConnectionError("Cannot submit job: not connected to Hadoop")

        try:
            fn = job_config.get("function")
            args = job_config.get("args", ())
            kwargs = job_config.get("kwargs", {})
            job_name = job_config.get(
                "job_name", getattr(fn, "__name__", "anonymous_task")
            )

            logger.info(f"Submitting job to Hadoop: {job_name}")

            # Serialize the job and upload to HDFS
            job_path = self._serialize_job(fn, args, kwargs)

            # Prepare MapReduce job
            job = self._job_client.create_job(
                name=job_name,
                queue="default",
                job_type="streaming",  # Using Hadoop Streaming API
            )

            # Set job parameters
            job.set_mapper("python /hadoop_executor/mapper.py")
            job.set_reducer("python /hadoop_executor/reducer.py")

            # Configure job paths
            job.set_input(job_path)
            job.set_output(
                f"/tmp/hadoop_executor/{self.username}/output/{job_name}_{int(time.time())}"
            )

            # Add job dependencies and settings
            job.add_file("/hadoop_executor/executor_runtime.py")  # Runtime support file
            job.set_property("hadoop.job.ugi", self.username)
            job.set_property("mapreduce.job.queuename", "default")

            # Submit the job
            job_id = job.submit()

            # Track the job
            self._job_results[job_id] = {
                "status": PENDING,
                "start_time": time.time(),
                "job_path": job_path,
                "output_path": job.get_output_path(),
                "job_name": job_name,
            }

            logger.info(f"Job submitted successfully with ID: {job_id}")
            return job_id

        except Exception as e:
            logger.error(f"Failed to submit job to Hadoop: {str(e)}")
            raise

    def get_job_status(self, job_id: str) -> str:
        """
        Get status of a submitted job.
        Args:
            job_id: Job identifier returned by submit_job.
        Returns:
            str: One of PENDING, RUNNING, FINISHED, CANCELLED, CANCELLED_AND_NOTIFIED.
        Raises:
            KeyError: If job_id is not found.
        """
        if job_id not in self._job_results:
            raise KeyError(f"Unknown job ID: {job_id}")

        # Query the actual status from YARN
        try:
            hadoop_status = self._job_client.get_job_status(job_id)

            # Map Hadoop-specific status to our status constants
            status_mapping = {
                "NEW": PENDING,
                "INITED": PENDING,
                "RUNNING": RUNNING,
                "SUCCEEDED": FINISHED,
                "FAILED": FINISHED,  # Still FINISHED, but will raise error on result retrieval
                "KILLED": CANCELLED,
                "ERROR": FINISHED,  # Still FINISHED, but will raise error on result retrieval
            }

            status = status_mapping.get(hadoop_status, RUNNING)

            # Update our tracking info
            self._job_results[job_id]["status"] = status
            if hadoop_status == "FAILED" or hadoop_status == "ERROR":
                self._job_results[job_id][
                    "error"
                ] = f"Job failed with status: {hadoop_status}"

            return status
        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {str(e)}")
            # Don't change tracked status on error
            return self._job_results[job_id]["status"]

    def get_job_result(self, job_id: str) -> typing.Any:
        """
        Get the result of a completed job.

        Args:
            job_id: Job identifier returned by submit_job.

        Returns:
            The result returned by the job function.

        Raises:
            KeyError: If job_id is not found.
            HadoopJobError: If the job failed with an error.
            RuntimeError: If the job is still pending or running.
        """
        if job_id not in self._job_results:
            raise KeyError(f"Unknown job ID: {job_id}")

        job_info = self._job_results[job_id]

        # Make sure the job is finished
        status = self.get_job_status(job_id)
        if status not in (FINISHED, CANCELLED, CANCELLED_AND_NOTIFIED):
            raise RuntimeError(f"Job {job_id} is not yet complete (status: {status})")

        # Check for errors
        if "error" in job_info and job_info["error"]:
            raise HadoopJobError(job_info["error"])

        # Read the result from HDFS
        try:
            import pickle

            output_path = job_info["output_path"]
            result_file = f"{output_path}/part-00000"

            if not self._hdfs_client.exists(result_file):
                # Try checking for other output parts
                files = self._hdfs_client.ls(output_path)
                result_files = [
                    f
                    for f in files
                    if f.endswith("part-00000") or f.endswith("part-r-00000")
                ]

                if not result_files:
                    raise HadoopJobError(
                        f"No result file found in output directory: {output_path}"
                    )

                result_file = result_files[0]

            # Read the serialized result
            with self._hdfs_client.open(result_file, "rb") as f:
                result = pickle.load(f)

            return result

        except Exception as e:
            raise HadoopJobError(f"Failed to retrieve job result: {str(e)}")

    def cancel_job(self, job_id: str) -> bool:
        """
        Attempt to cancel a job.

        Args:
            job_id: Job identifier returned by submit_job.

        Returns:
            bool: True if job was cancelled, False otherwise.
        """
        if job_id not in self._job_results:
            return False

        job_info = self._job_results[job_id]
        current_status = job_info["status"]

        if current_status in (FINISHED, CANCELLED, CANCELLED_AND_NOTIFIED):
            return False

        try:
            # Kill the job in YARN
            result = self._job_client.kill_job(job_id)

            if result:
                job_info["status"] = CANCELLED
                logger.info(f"Job {job_id} cancelled")
                return True
            else:
                logger.warning(f"Failed to cancel job {job_id}")
                return False

        except Exception as e:
            logger.error(f"Error while cancelling job {job_id}: {str(e)}")
            return False


class HadoopExecutor(Executor):
    """Executor that submits tasks to Hadoop for processing."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8020,
        username: str = None,
        password: str = None,
        kerb_ticket: str = None,
        hdfs_config: typing.Dict[str, str] = None,
        yarn_config: typing.Dict[str, str] = None,
        max_workers: int = None,
        poll_interval: float = 5.0,
    ):
        """
        Initialize the HadoopExecutor.

        Args:
            host: Hadoop namenode hostname.
            port: Hadoop namenode port.
            username: Username for authentication.
            password: Password for authentication.
            kerb_ticket: Path to Kerberos ticket file for authentication (alternative to password).
            hdfs_config: Additional HDFS configuration parameters.
            yarn_config: Additional YARN configuration parameters.
            max_workers: Maximum number of concurrent workers.
            poll_interval: Interval in seconds for polling job status.
        """
        self.connector = HadoopConnector(
            host=host,
            port=port,
            username=username,
            password=password,
            kerb_ticket=kerb_ticket,
            hdfs_config=hdfs_config,
            yarn_config=yarn_config,
        )
        self._max_workers = max_workers
        self._shutdown = False
        self._jobs = {}  # Maps futures to job IDs
        self._poll_interval = poll_interval
        self._polling_thread = None
        self._lock = threading.RLock()

        # Connect to Hadoop
        self.connector.connect()

        # Start polling thread
        self._start_polling_thread()

    def _start_polling_thread(self) -> None:
        """Start the background thread that polls for job status."""
        if self._polling_thread is None or not self._polling_thread.is_alive():
            self._polling_thread = threading.Thread(
                target=self._poll_jobs, daemon=True, name="HadoopExecutor-JobPoller"
            )
            self._polling_thread.start()

    def _poll_jobs(self) -> None:
        """Continuously poll for job status updates."""
        while not self._shutdown:
            try:
                with self._lock:
                    if not self._jobs:
                        time.sleep(self._poll_interval)
                        continue

                    # Make a copy to avoid modification during iteration
                    jobs_to_check = dict(self._jobs)

                for future, job_id in jobs_to_check.items():
                    if future.done():
                        continue

                    try:
                        status = self.connector.get_job_status(job_id)

                        if status == FINISHED:
                            try:
                                # Get the result from the job
                                result = self.connector.get_job_result(job_id)
                                future.set_result(result)
                                logger.debug(f"Job {job_id} completed")
                            except HadoopJobError as e:
                                future.set_exception(e)
                                logger.error(f"Job {job_id} failed: {str(e)}")

                        elif status in (CANCELLED, CANCELLED_AND_NOTIFIED):
                            if not future.cancelled():
                                future.cancel()
                            logger.debug(f"Job {job_id} was cancelled")

                        # For PENDING and RUNNING, continue polling

                    except Exception as exc:
                        logger.error(f"Error polling job {job_id}: {str(exc)}")
                        if not future.done():
                            future.set_exception(exc)

                time.sleep(self._poll_interval)

            except Exception as e:
                logger.error(f"Error in job polling thread: {str(e)}")
                time.sleep(self._poll_interval)

    def submit(self, fn: typing.Callable, /, *args, **kwargs) -> Future:
        """
        Submit a callable for execution on Hadoop.
        Args:
            fn: The callable to execute.
        Returns:
            Future: A Future representing the execution of the callable.
        Raises:
            RuntimeError: If the executor has been shut down.
            TypeError: If fn is not an EventBase instance.
        """
        with self._lock:
            if self._shutdown:
                raise RuntimeError("Cannot schedule new futures after shutdown")

            if not isinstance(fn, EventBase):
                raise TypeError("Tasks must be EventBase instances")

            future = Future()

            try:
                # Prepare job configuration
                job_config = {
                    "function": fn,
                    "args": args,
                    "kwargs": kwargs,
                    "job_name": getattr(fn, "__name__", "anonymous_task"),
                }

                # Submit to Hadoop
                job_id = self.connector.submit_job(job_config)

                # Track the job
                self._jobs[future] = job_id

                # The polling thread will handle status updates
                logger.debug(
                    f"Submitted task {job_config['job_name']} with job ID {job_id}"
                )

            except Exception as exc:
                future.set_exception(exc)
                logger.error(f"Error submitting task: {str(exc)}")

            return future

    def submit_batch(
        self, fns: typing.List[typing.Callable], *args_list
    ) -> typing.List[Future]:
        """
        Submit a batch of callables for execution on Hadoop.

        This is more efficient than calling submit() multiple times as it
        batches the submission process.
        Args:
            fns: List of callables to execute.
            *args_list: List of argument tuples, one per callable.
        Returns:
            List[Future]: A list of Futures representing the executions.
        """
        futures = []

        with self._lock:
            if self._shutdown:
                raise RuntimeError("Cannot schedule new futures after shutdown")

            # Make sure all tasks are EventBase instances
            for fn in fns:
                if not isinstance(fn, EventBase):
                    raise TypeError("All tasks must be EventBase instances")

            # Submit each task
            for i, fn in enumerate(fns):
                future = Future()
                futures.append(future)

                try:
                    # Get arguments for this task
                    if i < len(args_list):
                        if isinstance(args_list[i], tuple):
                            args = args_list[i]
                            kwargs = {}
                        elif isinstance(args_list[i], dict):
                            args = ()
                            kwargs = args_list[i]
                        else:
                            args = (args_list[i],)
                            kwargs = {}
                    else:
                        args = ()
                        kwargs = {}

                    # Prepare job configuration
                    job_config = {
                        "function": fn,
                        "args": args,
                        "kwargs": kwargs,
                        "job_name": getattr(fn, "__name__", f"batch_task_{i}"),
                    }

                    # Submit to Hadoop
                    job_id = self.connector.submit_job(job_config)

                    # Track the job
                    self._jobs[future] = job_id

                except Exception as exc:
                    future.set_exception(exc)

        return futures

    def cancel(self, future: Future) -> bool:
        """
        Cancel a submitted job.

        Args:
            future: Future representing the job to cancel.

        Returns:
            bool: True if cancellation was successful, False otherwise.
        """
        with self._lock:
            if future not in self._jobs:
                return False

            job_id = self._jobs[future]
            return self.connector.cancel_job(job_id)

    def shutdown(self, wait: bool = True) -> None:
        """
        Clean up the executor.

        Args:
            wait: If True, wait for all jobs to complete before shutting down.
        """
        with self._lock:
            logger.info("Shutting down HadoopExecutor")
            self._shutdown = True

            if wait:
                # Wait for all jobs to complete
                for future in list(self._jobs.keys()):
                    try:
                        logger.debug(f"Waiting for job to complete during shutdown")
                        future.result()
                    except Exception as e:
                        logger.error(f"Job failed during shutdown: {str(e)}")

            # Disconnect from Hadoop
            self.connector.disconnect()

            logger.info("HadoopExecutor shutdown complete")

    def __enter__(self) -> "HadoopExecutor":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.shutdown(wait=True)
