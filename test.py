from event_pipeline.parser import pointy_parser

ast = pointy_parser("A->B (0->C, 1->D, 2->E, 3->F, 4->A, 5->B)")
print(ast)

import pdb

pdb.set_trace()

"""
('->', 
 ('TASKNAME', 'A'), 
 ('GROUP', 
  ('TASKNAME', 'B'), 
  (
      (
          ('->', ('DESCRIPTOR', 0), ('TASKNAME', 'C')), 
          ('->', ('DESCRIPTOR', 1), ('TASKNAME', 'D'))
      ), 
      ('->', ('DESCRIPTOR', 2), ('TASKNAME', 'E'))
  )
  )
 )
"""
