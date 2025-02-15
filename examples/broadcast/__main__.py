from .broadcast import BroadcastPipeline

p = BroadcastPipeline(name="obrafour")
p.start(force_rerun=True)
p.draw_ascii_graph()
