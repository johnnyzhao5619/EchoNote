# Third-Party Licenses

EchoNote uses various third-party libraries and components. This document lists all third-party dependencies and their licenses to ensure compliance with open-source licensing requirements.

## License Compatibility

EchoNote is licensed under the **Apache License 2.0**. All third-party dependencies listed below are compatible with Apache 2.0 through their respective licenses.

---

## Runtime Dependencies

### UI Framework

#### PySide6 (Qt for Python)

- **License**: LGPL v3
- **Version**: >=6.6.0
- **Website**: https://www.qt.io/qt-for-python
- **Compatibility**: ✅ Compatible with Apache 2.0 through dynamic linking
- **Notes**:
  - PySide6 is the official Python binding for Qt from The Qt Company
  - Used under LGPL v3 license which allows commercial use when dynamically linked
  - EchoNote dynamically links to PySide6, maintaining full Apache 2.0 compatibility
  - No modifications to PySide6 source code
  - LGPL compliance: Users can replace PySide6 library without recompiling EchoNote

### Speech Recognition

#### Faster-Whisper

- **License**: MIT
- **Version**: >=0.10.0
- **Website**: https://github.com/guillaumekln/faster-whisper
- **Compatibility**: ✅ Fully compatible with Apache 2.0

#### PyTorch

- **License**: BSD-3-Clause
- **Version**: >=2.0.0
- **Website**: https://pytorch.org/
- **Compatibility**: ✅ Fully compatible with Apache 2.0

#### Torchaudio

- **License**: BSD-2-Clause
- **Version**: >=2.0.0
- **Website**: https://pytorch.org/audio/
- **Compatibility**: ✅ Fully compatible with Apache 2.0

#### Hugging Face Hub

- **License**: Apache 2.0
- **Version**: >=0.20.0
- **Website**: https://github.com/huggingface/huggingface_hub
- **Compatibility**: ✅ Same license as EchoNote

### Audio Processing

#### PyAudio

- **License**: MIT
- **Version**: >=0.2.13
- **Website**: https://people.csail.mit.edu/hubert/pyaudio/
- **Compatibility**: ✅ Fully compatible with Apache 2.0

#### SoundFile

- **License**: BSD-3-Clause
- **Version**: >=0.12.1
- **Website**: https://github.com/bastibe/python-soundfile
- **Compatibility**: ✅ Fully compatible with Apache 2.0

#### Librosa

- **License**: ISC
- **Version**: >=0.10.0
- **Website**: https://librosa.org/
- **Compatibility**: ✅ Fully compatible with Apache 2.0

#### WebRTC VAD

- **License**: BSD-3-Clause
- **Version**: >=2.0.10
- **Website**: https://github.com/wiseman/py-webrtcvad
- **Compatibility**: ✅ Fully compatible with Apache 2.0

### HTTP & Networking

#### HTTPX

- **License**: BSD-3-Clause
- **Version**: >=0.25.0
- **Website**: https://www.python-httpx.org/
- **Compatibility**: ✅ Fully compatible with Apache 2.0

#### Requests

- **License**: Apache 2.0
- **Version**: >=2.31.0
- **Website**: https://requests.readthedocs.io/
- **Compatibility**: ✅ Same license as EchoNote

#### Authlib

- **License**: BSD-3-Clause
- **Version**: >=1.2.0
- **Website**: https://authlib.org/
- **Compatibility**: ✅ Fully compatible with Apache 2.0

### Security & Encryption

#### Cryptography

- **License**: Apache 2.0 / BSD-3-Clause (dual-licensed)
- **Version**: >=41.0.0
- **Website**: https://cryptography.io/
- **Compatibility**: ✅ Same license as EchoNote

### Task Scheduling

#### APScheduler

- **License**: MIT
- **Version**: >=3.10.0
- **Website**: https://apscheduler.readthedocs.io/
- **Compatibility**: ✅ Fully compatible with Apache 2.0

### System Utilities

#### psutil

- **License**: BSD-3-Clause
- **Version**: >=5.9.0
- **Website**: https://github.com/giampaolo/psutil
- **Compatibility**: ✅ Fully compatible with Apache 2.0

#### python-dotenv

- **License**: BSD-3-Clause
- **Version**: >=1.0.0
- **Website**: https://github.com/theskumar/python-dotenv
- **Compatibility**: ✅ Fully compatible with Apache 2.0

---

## Development Dependencies

### Testing

#### pytest

- **License**: MIT
- **Version**: >=7.4.0
- **Compatibility**: ✅ Fully compatible with Apache 2.0

#### pytest-cov

- **License**: MIT
- **Version**: >=4.1.0
- **Compatibility**: ✅ Fully compatible with Apache 2.0

#### pytest-asyncio

- **License**: Apache 2.0
- **Version**: >=0.21.0
- **Compatibility**: ✅ Same license as EchoNote

#### pytest-qt

- **License**: MIT
- **Version**: >=4.2.0
- **Compatibility**: ✅ Fully compatible with Apache 2.0

#### pytest-mock

- **License**: MIT
- **Version**: >=3.11.0
- **Compatibility**: ✅ Fully compatible with Apache 2.0

### Code Quality

#### Black

- **License**: MIT
- **Version**: >=23.7.0
- **Compatibility**: ✅ Fully compatible with Apache 2.0

#### Pylint

- **License**: GPL v2
- **Version**: >=2.17.0
- **Compatibility**: ✅ Development tool only, not distributed

#### Flake8

- **License**: MIT
- **Version**: >=6.1.0
- **Compatibility**: ✅ Fully compatible with Apache 2.0

#### MyPy

- **License**: MIT
- **Version**: >=1.5.0
- **Compatibility**: ✅ Fully compatible with Apache 2.0

#### isort

- **License**: MIT
- **Version**: >=5.12.0
- **Compatibility**: ✅ Fully compatible with Apache 2.0

#### pre-commit

- **License**: MIT
- **Version**: >=3.3.0
- **Compatibility**: ✅ Fully compatible with Apache 2.0

### Build Tools

#### PyInstaller

- **License**: GPL v2 with exception
- **Version**: >=5.13.0
- **Compatibility**: ✅ Build tool only, not distributed
- **Notes**: PyInstaller's GPL license with bootloader exception allows commercial distribution

#### py2app

- **License**: MIT
- **Version**: >=0.28.0
- **Compatibility**: ✅ Fully compatible with Apache 2.0

---

## License Summaries

### MIT License

Permissive license allowing commercial use, modification, distribution, and private use. Compatible with Apache 2.0.

### BSD Licenses (2-Clause, 3-Clause)

Permissive licenses similar to MIT, allowing commercial use with minimal restrictions. Fully compatible with Apache 2.0.

### Apache License 2.0

Same license as EchoNote. Provides patent grant and requires preservation of copyright notices.

### ISC License

Functionally equivalent to MIT and BSD 2-Clause. Fully compatible with Apache 2.0.

### LGPL v3 (PySide6)

Copyleft license that requires:

- Providing source code or object files for LGPL components
- Allowing users to replace LGPL libraries
- Maintaining LGPL license for LGPL components

**EchoNote's LGPL Compliance**:

- PySide6 is dynamically linked (not statically compiled)
- Users can replace PySide6 without recompiling EchoNote
- No modifications made to PySide6 source code
- This allows EchoNote to remain Apache 2.0 licensed

---

## Compliance Checklist

For distributors and users of EchoNote:

- ✅ All runtime dependencies are compatible with Apache 2.0
- ✅ PySide6 (LGPL v3) is used through dynamic linking
- ✅ No GPL-licensed components in runtime distribution
- ✅ Development tools (GPL-licensed) are not distributed
- ✅ All license texts are preserved in this document
- ✅ Copyright notices are maintained in source files

---

## Additional Resources

### License Texts

Full license texts for all dependencies can be found in:

- Python packages: `site-packages/<package>-<version>.dist-info/LICENSE`
- This project: `LICENSE` file (Apache 2.0)

### Qt Licensing

For detailed information about Qt and PySide6 licensing:

- Qt Licensing: https://www.qt.io/licensing/
- PySide6 Documentation: https://doc.qt.io/qtforpython/
- LGPL v3 Text: https://www.gnu.org/licenses/lgpl-3.0.html

### Verification

To verify licenses of installed packages:

```bash
pip-licenses --format=markdown --with-urls
```

---

## Updates

This document should be updated whenever:

- New dependencies are added
- Dependency versions are significantly updated
- License terms change for any dependency

**Last Updated**: October 30, 2025  
**EchoNote Version**: 1.1.0

---

## Contact

For licensing questions or concerns:

- Open an issue: https://github.com/johnnyzhao5619/echonote/issues
- Email: [Contact information]

---

**Disclaimer**: This document is provided for informational purposes. Users should verify license compatibility for their specific use case. When in doubt, consult with a legal professional.
