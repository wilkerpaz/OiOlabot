{ config, pkgs, ... }:

{
  systemd.services = {
    oiolabot-main = {
      description = "OiOlabot - Main Bot (welcome + RSS)";
      after = [ "network.target" "redis.service" ];
      wants = [ "redis.service" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "simple";
        User = "oiolabot";
        Group = "oiolabot";
        WorkingDirectory = "/opt/oiolabot";
        EnvironmentFile = "/opt/oiolabot/.env";
        ExecStart = "${pkgs.python311}/bin/python main.py";
        Restart = "on-failure";
        RestartSec = 10;
      };
    };

    oiolabot-liturgy = {
      description = "OiOlabot - Liturgy Bot (daily readings)";
      after = [ "network.target" "redis.service" ];
      wants = [ "redis.service" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "simple";
        User = "oiolabot";
        Group = "oiolabot";
        WorkingDirectory = "/opt/oiolabot";
        EnvironmentFile = "/opt/oiolabot/.env";
        ExecStart = "${pkgs.python311}/bin/python liturgy.py";
        Restart = "on-failure";
        RestartSec = 10;
      };
    };

    oiolabot-worker = {
      description = "OiOlabot - Worker (feed distribution + scheduler)";
      after = [ "network.target" "redis.service" ];
      wants = [ "redis.service" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "simple";
        User = "oiolabot";
        Group = "oiolabot";
        WorkingDirectory = "/opt/oiolabot";
        EnvironmentFile = "/opt/oiolabot/.env";
        ExecStart = "${pkgs.python311}/bin/python worker.py";
        Restart = "on-failure";
        RestartSec = 10;
        TimeoutStopSec = 60;
      };
    };
  };

  systemd.timers.oiolabot-watchdog = {
    description = "OiOlabot - Watchdog timer (checks services every 15min)";
    wantedBy = [ "timers.target" ];
    timerConfig = {
      OnBootSec = "2min";
      OnUnitActiveSec = "15min";
    };
  };

  systemd.services.oiolabot-watchdog = {
    description = "OiOlabot - Watchdog (restarts down services, alerts via Telegram)";
    serviceConfig = {
      Type = "oneshot";
      User = "oiolabot";
      Group = "oiolabot";
      WorkingDirectory = "/opt/oiolabot";
      EnvironmentFile = "/opt/oiolabot/.env";
      ExecStart = "${pkgs.python311}/bin/python watchdog.py";
    };
  };
}
