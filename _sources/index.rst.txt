.. Event Pipeline documentation master file, created by
   sphinx-quickstart on Sat Mar  1 02:47:26 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Event Pipeline
=============

.. image:: ../../img/pipeline.svg
   :height: 60px
   :width: 60px
   :align: left
   :alt: pipeline

|build-status| |code-style| |status| |latest| |pyv| |prs|

.. |build-status| image:: https://github.com/nshaibu/event_pipeline/actions/workflows/python_package.yml/badge.svg
   :target: https://github.com/nshaibu/event_pipeline/actions

.. |code-style| image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black

.. |status| image:: https://img.shields.io/pypi/status/event-pipeline.svg
   :target: https://pypi.python.org/pypi/event-pipeline

.. |latest| image:: https://img.shields.io/pypi/v/event-pipeline.svg
   :target: https://pypi.python.org/pypi/event-pipeline

.. |pyv| image:: https://img.shields.io/pypi/pyversions/event-pipeline.svg
   :target: https://pypi.python.org/pypi/event-pipeline

.. |prs| image:: https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square
   :target: http://makeapullrequest.com

Introduction
-----------
This library provides an easy-to-use framework for defining and managing events and pipelines. 
It allows you to create events, process data through a series of tasks, and manage complex workflows
with minimal overhead. The library is designed to be extensible and flexible, enabling developers to 
easily integrate it into their projects.

Features
~~~~~~~~
- Define and manage events and pipelines in Python
- Support for conditional task execution
- Easy integration of custom event processing logic
- Supports remote task execution and distributed processing
- Seamless handling of task dependencies and event execution flow

Installation
~~~~~~~~~~~
To install the library, simply use pip:

.. code-block:: bash

   pip install event-pipeline

Requirements
~~~~~~~~~~~
- Python>=3.8
- ply==3.11 
- treelib==1.7.0
- more-itertools<=10.6.0
- apscheduler<=3.11.0
- graphviz==0.20.3 (Optional)

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   tutorials/index
   usage/pipeline
   usage/events
   usage/scheduling
   usage/signals
   usage/telemetry
   usage/contributing
   api/index

