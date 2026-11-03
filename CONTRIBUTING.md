# Contributing to EtherPocket

## Preparation

Clone the repository and create a branch, for example `git switch -c docs/component-overview`. Read the component README, its `CMakeLists.txt` and the relevant build script. Qt libraries, system dependencies and the ARM64 toolchain vary by component. Ordinary host tests do not require administrator access to the phone.

## Tests without a device

On Windows and Linux:

```sh
python -m unittest discover -s tests -p test_x11.py
python -m unittest discover -s etherpocket-control -p test_transport.py
```

Additionally, on Linux:

```sh
python3 -m unittest discover -s tests -p test_mobile_data_status.py
PYTHONPATH=scripts python3 -m unittest discover -s tests -p test_ethermobile_data_cleanup.py
```

The second group relies on POSIX behavior, including `O_NOFOLLOW`. Do not weaken production security controls to run these tests on Windows. CI runs the listed tests on Linux and the portable tests on Windows. It does not build a complete system image, boot a phone or verify hardware features.

## Changes and review

- Describe the concrete problem and resulting behavior.
- State the tests performed, environment and limits of the results.
- For hardware changes, add a dated report in `docs/`, the device model and recovery procedure.
- Update `docs/STATUS.md` when new evidence changes feature readiness.
- Use English for new repository documentation, issues, pull requests and commit messages. Explicitly localized materials may retain their target language.
- Use UTF-8. Python, shell scripts and Linux files use LF. Windows scripts use CRLF.

## Device operations and local data

Read flashing, partitioning, activation and call-test scripts before running them. Check device identity and script assumptions. Scripts often reference the author's existing local key paths and USB address. A new workstation needs its own SSH authorization and host verification.

Do not commit keys, tokens, Wi-Fi passwords, NetworkManager profiles, partition backups, contact databases or private media. Keep raw results locally in `evidence/`. Review and anonymize material before moving it into `docs/` for publication. `.gitignore` reduces accidental additions but does not replace reviewing `git diff --cached`.

## Licensing

Do not add a project-wide license before establishing the rights covering its components and external code. Preserve existing author notices and terms of use.
