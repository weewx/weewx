from setup import ExtensionInstaller

def loader():
    return PrevimeteoInstaller()

class PrevimeteoInstaller(ExtensionInstaller):
    def __init__(self):
        super(PrevimeteoInstaller, self).__init__(
            version="0.1",
            name='previmeteo',
            description='Upload weather data to Previmeteo',
            author="Jean-Pierre Bouchillou",
            author_email="support@previmeteo.com",
            restful_services='user.previmeteo.Previmeteo',
            config={
                'StdRESTful': {
                    'Previmeteo': {
                        'station': 'INSERT_USERNAME_HERE',
                        'password': 'INSERT_PASSWORD_HERE'}}},
            files=[('bin/user', ['bin/user/previmeteo.py'])]
            )
