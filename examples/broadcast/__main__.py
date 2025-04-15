#
import broadcast

p = broadcast.BroadcastPipeline(name="obrafour")
p.start(force_rerun=True)
# p.draw_ascii_graph()
# p.draw_graphviz_image()
