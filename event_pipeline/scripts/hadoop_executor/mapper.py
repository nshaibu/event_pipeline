#!/usr/bin/env python
import sys
import pickle
import traceback


def map_execute():
    try:
        # Load the job information from HDFS
        job_path = sys.argv[1]
        with open(job_path, "rb") as f:
            fn, args, kwargs = pickle.load(f)

        # Execute the function
        result = fn(*args, **kwargs)

        # Output the result
        print("result\t", end="")
        sys.stdout.buffer.write(pickle.dumps(result))

    except Exception as e:
        print("error\t", end="")
        error_info = {"error": str(e), "traceback": traceback.format_exc()}
        sys.stdout.buffer.write(pickle.dumps(error_info))


if __name__ == "__main__":
    map_execute()
