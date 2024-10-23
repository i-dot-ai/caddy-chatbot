import os


class HostingEnvironment:
    @staticmethod
    def is_dev():
        return os.getenv("STAGE") == "dev"
