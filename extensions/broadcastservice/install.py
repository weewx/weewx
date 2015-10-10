# installer for the broadcastservice
# Copyright 2015 Jakub Kakona

from setup import ExtensionInstaller

def loader():
    return FileParseInstaller()

class FileParseInstaller(ExtensionInstaller):
    def __init__(self):
        super(FileParseInstaller, self).__init__(
            version="0.1",
            name='broadcastservice',
            description='Data publishing on local network',
            author="Jakub Kakona",
            author_email="kaklik@mlab.cz",
            config={
                },
            files=[('bin/user', ['bin/user/broadcastservice.py'])]
            )
