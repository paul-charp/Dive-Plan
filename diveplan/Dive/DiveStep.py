class DiveStep():
    """docstring for DiveStep."""
    def __init__(self, time, samplerate, start_depth, end_depth, gas):
        super(DiveStep, self).__init__()
        self.time = time
        self.samplerate = samplerate
        self.start_depth = start_depth
        self.end_depth = end_depth
        self.gas = gas

    