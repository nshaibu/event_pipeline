from .simple import Simple

s = Simple(name="home")
s.start(force_rerun=True)
s.draw_ascii_graph()
