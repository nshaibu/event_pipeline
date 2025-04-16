from broadcast import BroadcastPipeline

if __name__ == "__main__":
    p = BroadcastPipeline(name="obrafour")
    p.start(force_rerun=True)
