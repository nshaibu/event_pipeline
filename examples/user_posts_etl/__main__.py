from .etl_pipeline import UserPostETLPipeline

pipeline = UserPostETLPipeline()

pipeline.start()

# To draw ascii graph
# pipeline.draw_ascii_graph()

# To draw graphviz image
# pipeline.draw_graphviz_image()
