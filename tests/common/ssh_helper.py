import paramiko


class SshHelper:

    def __init__(self, host: str, username: str, password: str):
        self.__host = host
        self.__username = username
        self.__password = password

        self.__ssh = paramiko.SSHClient()
        self.__ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self):
        try:
            self.__ssh.connect(self.__host, username=self.__username, password=self.__password)
        except Exception as exception:
            print(f"connect() exception occurred: {exception}")
            return False

        return True

    def close(self):
        self.__ssh.close()
