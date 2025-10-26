# Third-Party Licenses

This document lists all third-party dependencies used by EchoNote and their respective licenses. EchoNote is licensed under Apache 2.0, and all dependencies listed here are compatible with this license.

## License Compatibility Summary

- **Apache 2.0** (EchoNote): Permissive license allowing commercial use
- **LGPL v3** (PySide6): Copyleft license requiring dynamic linking compliance
- **MIT/BSD/Apache 2.0** (Most other dependencies): Permissive licenses fully compatible

## Critical License Notice: PySide6 (LGPL v3)

**PySide6** is licensed under the **GNU Lesser General Public License v3 (LGPL v3)**, which requires specific compliance measures:

### LGPL v3 Compliance Requirements

1. **Dynamic Linking**: EchoNote uses PySide6 as a dynamically linked library, which is permitted under LGPL v3
2. **Source Code Availability**: Users must be able to access PySide6 source code
3. **Library Replacement**: Users must be able to replace the PySide6 library with a different version

### PySide6 Source Code and Information

- **Official Website**: https://www.qt.io/qt-for-python
- **Source Code Repository**: https://code.qt.io/cgit/pyside/pyside-setup.git/
- **License Text**: https://www.gnu.org/licenses/lgpl-3.0.html
- **Qt Company**: PySide6 is officially maintained by The Qt Company

### How to Replace PySide6

Users can replace the PySide6 library by:

1. **Using pip**: `pip uninstall PySide6 && pip install PySide6==<desired-version>`
2. **Using conda**: `conda remove PySide6 && conda install PySide6=<desired-version>`
3. **Manual installation**: Download and install PySide6 wheels from PyPI
4. **Building from source**: Compile PySide6 from the official source repository

The application will work with any compatible PySide6 version (>= 6.6.0) without requiring recompilation of EchoNote itself.

## Production Dependencies

### UI Framework

| Package | Version  | License | Website                         |
| ------- | -------- | ------- | ------------------------------- |
| PySide6 | >= 6.6.0 | LGPL v3 | https://www.qt.io/qt-for-python |

### Speech Recognition & Machine Learning

| Package         | Version   | License      | Website                                        |
| --------------- | --------- | ------------ | ---------------------------------------------- |
| faster-whisper  | >= 0.10.0 | MIT          | https://github.com/guillaumekln/faster-whisper |
| torch           | >= 2.0.0  | BSD-3-Clause | https://pytorch.org/                           |
| torchaudio      | >= 2.0.0  | BSD-2-Clause | https://pytorch.org/audio/                     |
| huggingface-hub | >= 0.20.0 | Apache 2.0   | https://github.com/huggingface/huggingface_hub |

### Audio Processing

| Package   | Version   | License      | Website                                      |
| --------- | --------- | ------------ | -------------------------------------------- |
| PyAudio   | >= 0.2.13 | MIT          | https://people.csail.mit.edu/hubert/pyaudio/ |
| soundfile | >= 0.12.1 | BSD-3-Clause | https://github.com/bastibe/python-soundfile  |
| librosa   | >= 0.10.0 | ISC          | https://librosa.org/                         |
| webrtcvad | >= 2.0.10 | MIT          | https://github.com/wiseman/py-webrtcvad      |

### HTTP & API

| Package  | Version   | License      | Website                          |
| -------- | --------- | ------------ | -------------------------------- |
| httpx    | >= 0.25.0 | BSD-3-Clause | https://www.python-httpx.org/    |
| requests | >= 2.31.0 | Apache 2.0   | https://requests.readthedocs.io/ |
| authlib  | >= 1.2.0  | BSD-3-Clause | https://authlib.org/             |

### Security & Encryption

| Package      | Version   | License                   | Website                  |
| ------------ | --------- | ------------------------- | ------------------------ |
| cryptography | >= 41.0.0 | Apache 2.0 / BSD-3-Clause | https://cryptography.io/ |

### Task Scheduling & Utilities

| Package       | Version   | License      | Website                                    |
| ------------- | --------- | ------------ | ------------------------------------------ |
| APScheduler   | >= 3.10.0 | MIT          | https://apscheduler.readthedocs.io/        |
| python-dotenv | >= 1.0.0  | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| psutil        | >= 5.9.0  | BSD-3-Clause | https://github.com/giampaolo/psutil        |

## Development Dependencies

### Testing Framework

| Package        | Version   | License    | Website                                      |
| -------------- | --------- | ---------- | -------------------------------------------- |
| pytest         | >= 7.4.0  | MIT        | https://pytest.org/                          |
| pytest-cov     | >= 4.1.0  | MIT        | https://github.com/pytest-dev/pytest-cov     |
| pytest-asyncio | >= 0.21.0 | Apache 2.0 | https://github.com/pytest-dev/pytest-asyncio |
| pytest-qt      | >= 4.2.0  | MIT        | https://github.com/pytest-dev/pytest-qt      |
| pytest-mock    | >= 3.11.0 | MIT        | https://github.com/pytest-dev/pytest-mock    |

### Code Quality Tools

| Package    | Version   | License | Website                        |
| ---------- | --------- | ------- | ------------------------------ |
| black      | >= 23.7.0 | MIT     | https://black.readthedocs.io/  |
| pylint     | >= 2.17.0 | GPL v2  | https://pylint.pycqa.org/      |
| flake8     | >= 6.1.0  | MIT     | https://flake8.pycqa.org/      |
| mypy       | >= 1.5.0  | MIT     | https://mypy.readthedocs.io/   |
| isort      | >= 5.12.0 | MIT     | https://pycqa.github.io/isort/ |
| pre-commit | >= 3.3.0  | MIT     | https://pre-commit.com/        |

### Documentation

| Package                  | Version   | License      | Website                                             |
| ------------------------ | --------- | ------------ | --------------------------------------------------- |
| sphinx                   | >= 7.1.0  | BSD-2-Clause | https://www.sphinx-doc.org/                         |
| sphinx-rtd-theme         | >= 1.3.0  | MIT          | https://github.com/readthedocs/sphinx_rtd_theme     |
| sphinx-autodoc-typehints | >= 1.24.0 | MIT          | https://github.com/tox-dev/sphinx-autodoc-typehints |

### Build & Packaging Tools

| Package     | Version   | License               | Website                        |
| ----------- | --------- | --------------------- | ------------------------------ |
| pyinstaller | >= 5.13.0 | GPL v2 with exception | https://pyinstaller.org/       |
| py2app      | >= 0.28.0 | MIT                   | https://py2app.readthedocs.io/ |

### Type Stubs

| Package        | Version   | License    | Website                                 |
| -------------- | --------- | ---------- | --------------------------------------- |
| types-requests | >= 2.31.0 | Apache 2.0 | https://github.com/python/typeshed      |
| PySide6-stubs  | >= 6.5.0  | LGPL v3    | https://pypi.org/project/PySide6-stubs/ |

## License Texts

### LGPL v3 (PySide6)

The complete LGPL v3 license text can be found at: https://www.gnu.org/licenses/lgpl-3.0.html

### MIT License

```
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### BSD-3-Clause License

```
BSD 3-Clause License

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

### Apache 2.0 License

The complete Apache 2.0 license text can be found in the LICENSE file in the root directory of this project.

## Compliance Notes

1. **LGPL v3 Compliance**: EchoNote complies with LGPL v3 requirements by using PySide6 as a dynamically linked library and providing clear instructions for library replacement.

2. **GPL v2 Tools**: Some development tools (pylint, pyinstaller) use GPL v2, but these are only used during development and are not distributed with the final application.

3. **Commercial Use**: All production dependencies are compatible with commercial use and distribution.

4. **Attribution**: While not legally required for most licenses, we acknowledge and thank all the open-source contributors whose work makes EchoNote possible.

## Updates

This document should be updated whenever dependencies are added, removed, or their versions are significantly changed. The license information was last verified on the date of the PySide6 migration.

For questions about license compliance, please consult with legal counsel or contact the EchoNote maintainers.
