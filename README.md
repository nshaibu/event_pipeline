# event_pipeline
Simple tool for writing events and pipelines in python

- Single Task:

A

- Two tasks with result piping

A|->B

- Multiple tasks with branching

A->B(0->C,1->D)

- Multiple tasks with sink

A(0->B,1->C)->D

# Example

A->B(0->C->D(),1->E)|->F