import os


class HostingEnvironment:
    @staticmethod
    def is_dev():
        return os.getenv("STAGE") == "dev"

    @staticmethod
    def is_test():
        return os.getenv("STAGE") == "test"
