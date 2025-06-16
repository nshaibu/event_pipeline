from .etl_pipeline import UserPostETLPipeline

pipeline = UserPostETLPipeline()

pipeline.start()
# pipeline.draw_ascii_graph() #To draw ascii graph
# pipeline.draw_graphviz_image() #To draw graphviz image
