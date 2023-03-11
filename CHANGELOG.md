# Changelog

## [2.1.1] - 2023-03-10

### Fixed
- Change log level from error to info when audio driver can't be loaded at startup (surely no hardware)
- Move default sound files from core in brand new assets directory
- #1386 error installing "usb audio driver" issue

### Changed
- Improve unit tests

## [2.1.0] - 2022-01-16

### Changed
- Update app and bcm driver after core changes on audiodriver
- Improvement to avoid app crash while loading invalid driver
- Restart Cleep after new audio device has been selected (this allow reset Gstreamer context)
- Improve code coverage

### Added
* Add USB driver to handle USB audio hardware

## [2.0.4] - 2021-06-02

* Update driver stuff after core changes

## [2.0.3] - 2021-05-04

* Backend: do not reboot after driver install/uninstall
* Frontend: fix layout

## [2.0.2] - 2021-04-18

* Update after core changes
* Lint code
* Fix tests

## [2.0.1] - 2020-12-30

* Small UI fix
* Fix audio driver which changed new raspberry pi os

## [2.0.0] - 2020-12-13

* Migrate to python3
* Add unit tests
* Clean code
* Fix issues

## [1.1.0] - 2019-09-30

* Update after core changes
* Layout improvments
* Implement new driver core feature
* Fix issues

## [1.0.1] - 2018-10-14

* Fix small issues

## [1.0.0] - 2018-10-08

* First release

