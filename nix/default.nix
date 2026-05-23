{ pkgs ? import <nixpkgs> { } }:

pkgs.python311.withPackages (ps: with ps; [
  # Core framework
  kurigram

  # Data & cache
  redis
  feedparser
  beautifulsoup4
  lxml

  # HTTP
  httpx

  # Scheduler
  apscheduler

  # Config & utilities
  python-decouple
  pytz
  python-dateutil
])
