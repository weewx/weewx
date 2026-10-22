from unittest import mock

import pytest

import weeutil.ftpupload


@pytest.mark.parametrize('excluded', ['.git', '.svn', 'CVS', '__pycache__', '.idea'])
def test_upload_prunes_excluded_descendants(tmp_path, excluded):
    hidden = tmp_path / 'nested' / excluded / 'objects' / 'ab'
    hidden.mkdir(parents=True)
    (hidden / 'object').write_text('excluded')
    public = tmp_path / 'weather' / 'nested'
    public.mkdir(parents=True)
    (public / 'index.html').write_text('weather')
    uploads = []
    ftp = mock.Mock()
    ftp.storbinary.side_effect = lambda command, stream: uploads.append(command)
    with mock.patch.object(weeutil.ftpupload.ftplib, 'FTP', return_value=ftp):
        uploader = weeutil.ftpupload.FtpUpload('example.invalid', 'user', 'password',
                                              str(tmp_path), '/weather')
        assert uploader.run() == 1
        assert len(uploads) == 1
        assert uploads[0].endswith('/weather/nested/index.html')
