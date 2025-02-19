
class Connection:
    def __init__(self, connection):
        self.connection = connection
        self.cursor = connection.cursor()

    def runshell(self):
        pass
