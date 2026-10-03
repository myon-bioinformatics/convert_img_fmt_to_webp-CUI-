# convert_img_fmt_to_webp-CUI-
## Summary
![WebP_IMAGE](https://developers.google.com/static/speed/webp/images/webplogo.png)

__convert image files(format: png,ipg,jpeg,gif,svg) to webp file__

![GitHub license](https://img.shields.io/github/license/myon-bioinformatics/convert_img_fmt_to_webp-CUI-)
![GitHub last commit](https://img.shields.io/github/last-commit/myon-bioinformatics/convert_img_fmt_to_webp-CUI-)

[![GitHub followers](https://img.shields.io/github/followers/myon-bioinformatics?style=social)](https://github.com/myon-bioinformatics)
[![Reddit User Karma](https://img.shields.io/reddit/user-karma/combined/myon_reddit?style=social)](https://www.reddit.com/user/myon_reddit/)
[![Twitter Follow](https://img.shields.io/twitter/follow/myonitbusiness?style=social)](https://twitter.com/myonitbusiness)


## Note/Warning
> __Note__ You must install "PySimpleGUI" and pillow by pip, if not.

> __Warning__ Unless you understand "Docker" or not want to install "PySimpleGUI", I recommend using GUI version

## References
- About Pillow: https://pypi.org/project/Pillow
- About GUI version: [convert_img_fmt_to_webp-GUI-](https://github.com/myon-bioinformatics/convert_img_fmt_to_webp-GUI-)
- About Webp: https://developers.google.com/speed/webp

## Tests and CI diagnostics

Pillow remains the runtime dependency in `requirements.txt`. Test tooling is
separate in `tests/requirements.txt` and is not installed into the runtime image.

```bash
python -m pip install -r requirements.txt -r tests/requirements.txt
python -m pytest -q tests --junitxml=reports/pytest-local.xml
```

CI runs the real conversion smoke test on Python 3.10, 3.12 and 3.14 and
preserves each JUnit report even when tests fail. A pinned shared collector
uses xprobe to produce compact failure identities and rejects missing reports.
Git commit identity is left null until canonical metadata is measured. Raw
reports stay in Actions artifacts; Docker conversion checks run independently
with only runtime dependencies installed.

The inactive CodeQL workflow has been removed by project policy. xprobe collects
test failure evidence; it does not replace static vulnerability analysis.

CI also loads a pinned, test-only xprobe pytest adapter and preserves one native
JSONL observation artifact per Python version. These records retain pytest
phase/outcome distinctions such as setup/call/teardown, xfail and xpass while
omitting captured output, traceback, marker reasons and parameter values.
Commit SHA remains unmeasured/null until canonical repository metadata is wired;
the workflow does not substitute `GITHUB_SHA`. Native JSONL complements the
existing JUnit compatibility collector and is not published to Pages.


Test-only adapter placement and automatic CI updates are described in
[Public vendor placement in CI](docs/vendor-automation.md).
