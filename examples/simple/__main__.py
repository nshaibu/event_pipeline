from .simple import Simple, SimpleBatch

# s = Simple(name="home")
# s.start(force_rerun=True)
# s.draw_ascii_graph()

batch = SimpleBatch(name=list(range(100)))
batch.execute()
