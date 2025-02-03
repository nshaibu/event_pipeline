from pipeline.parser import pointy_parser
from pipeline.task import PipelineTask

ast = pointy_parser("Fetch->Process->Execute(0->C, 1|->B->C)->SaveToDB->Return")


# import pdb
#
# pdb.set_trace()

pipe = PipelineTask.parse_ast(ast)


# (
#     "->",
#     (
#         "->",
#         (
#             "->",
#             ("->", ("TASKNAME", "Fetch"), ("TASKNAME", "Process")),
#             ("TASKNAME", "Execute"),
#         ),
#         ("TASKNAME", "SaveToDB"),
#     ),
#     ("TASKNAME", "Return"),
# )


# (
#     "->",
#     (
#         "->",
#         (
#             "->",
#             ("->", ("TASKNAME", "Fetch"), ("TASKNAME", "Process")),
#             (
#                 "GROUP",
#                 ("TASKNAME", "Execute"),
#                 ("->", ("DESCRIPTOR", "0"), ("TASKNAME", "C")),
#                 (
#                     "->",
#                     ("|->", ("DESCRIPTOR", "1"), ("TASKNAME", "B")),
#                     ("TASKNAME", "C"),
#                 ),
#             ),
#         ),
#         ("TASKNAME", "SaveToDB"),
#     ),
#     ("TASKNAME", "Return"),
# )
