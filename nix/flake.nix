{
  description = "TCG Automation - Pokemon TCG inventory for Odoo";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        
        pythonPackages = pkgs.python311Packages;
        
        tcg-automation = pythonPackages.buildPythonApplication {
          pname = "tcg-automation";
          version = "1.0.0";
          
          src = ../.;
          format = "pyproject";
          
          nativeBuildInputs = with pythonPackages; [
            hatchling
          ];
          
          propagatedBuildInputs = with pythonPackages; [
            click
            requests
            python-dotenv
            rich
            reportlab
            python-barcode
            qrcode
            pillow
            flask
            flask-cors
          ];
          
          # Skip tests for now
          doCheck = false;
          
          meta = with pkgs.lib; {
            description = "Pokemon TCG automation for Odoo ERP";
            homepage = "https://github.com/jleyva816/tcg-automation";
            license = licenses.mit;
            maintainers = [];
          };
        };
        
      in {
        packages = {
          default = tcg-automation;
          tcg-automation = tcg-automation;
        };
        
        apps.default = {
          type = "app";
          program = "${tcg-automation}/bin/tcg";
        };
        
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python311
            python311Packages.pip
            python311Packages.virtualenv
          ];
          
          shellHook = ''
            echo "TCG Automation Development Shell"
            echo "Run: pip install -e ."
          '';
        };
      }
    ) // {
      # NixOS module for systemd service
      nixosModules.default = { config, lib, pkgs, ... }:
        with lib;
        let
          cfg = config.services.tcg-automation;
        in {
          options.services.tcg-automation = {
            enable = mkEnableOption "TCG Automation scanner service";
            
            package = mkOption {
              type = types.package;
              default = self.packages.${pkgs.system}.default;
              description = "TCG Automation package to use";
            };
            
            port = mkOption {
              type = types.port;
              default = 5000;
              description = "Port for the scanner web server";
            };
            
            odooUrl = mkOption {
              type = types.str;
              example = "http://192.168.10.105:8069";
              description = "Odoo server URL";
            };
            
            odooDb = mkOption {
              type = types.str;
              example = "TCG-Cards";
              description = "Odoo database name";
            };
            
            odooUser = mkOption {
              type = types.str;
              description = "Odoo username";
            };
            
            odooPasswordFile = mkOption {
              type = types.path;
              description = "Path to file containing Odoo password";
            };
          };
          
          config = mkIf cfg.enable {
            systemd.services.tcg-scanner = {
              description = "TCG Card Scanner";
              wantedBy = [ "multi-user.target" ];
              after = [ "network.target" ];
              
              serviceConfig = {
                Type = "simple";
                ExecStart = "${cfg.package}/bin/tcg server --port ${toString cfg.port} --no-debug";
                Restart = "on-failure";
                RestartSec = 5;
                
                # Security hardening
                DynamicUser = true;
                ProtectSystem = "strict";
                ProtectHome = true;
                NoNewPrivileges = true;
              };
              
              environment = {
                ODOO_URL = cfg.odooUrl;
                ODOO_DB = cfg.odooDb;
                ODOO_USER = cfg.odooUser;
              };
              
              script = ''
                export ODOO_PASSWORD=$(cat ${cfg.odooPasswordFile})
                exec ${cfg.package}/bin/tcg server --port ${toString cfg.port} --no-debug
              '';
            };
            
            # Daily price sync timer
            systemd.services.tcg-price-sync = {
              description = "TCG Price Sync";
              
              serviceConfig = {
                Type = "oneshot";
                ExecStart = "${cfg.package}/bin/tcg sync";
                
                DynamicUser = true;
                ProtectSystem = "strict";
                ProtectHome = true;
              };
              
              environment = {
                ODOO_URL = cfg.odooUrl;
                ODOO_DB = cfg.odooDb;
                ODOO_USER = cfg.odooUser;
              };
              
              script = ''
                export ODOO_PASSWORD=$(cat ${cfg.odooPasswordFile})
                exec ${cfg.package}/bin/tcg sync
              '';
            };
            
            systemd.timers.tcg-price-sync = {
              description = "Daily TCG price sync";
              wantedBy = [ "timers.target" ];
              timerConfig = {
                OnCalendar = "daily";
                Persistent = true;
                RandomizedDelaySec = "1h";
              };
            };
          };
        };
    };
}


