{
  pkgs,
  lib,
  config,
  inputs,
  ...
}: {
  languages.javascript = {
    enable = true;
    pnpm.enable = true;
    pnpm.install.enable = true;
  };
  languages.typescript.enable = true;
}
