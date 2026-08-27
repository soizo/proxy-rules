const BASE_URL =
  "https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/";
const PREFERRED_PROXY_GROUPS = [
  "Proxy",
  "PROXY",
  "proxy",
  "节点选择",
  "🚀 节点选择",
  "选择节点",
  "🔰 选择节点",
];
// BEGIN GENERATED FIXED PROVIDERS
const FIXED_PROVIDERS = {
  "fixed-direct": "fixed-direct.txt",
  "fixed-proxy": "fixed-proxy.txt",
};
// END GENERATED FIXED PROVIDERS
const MODULE_PROVIDERS = {
  "module-direct": "direct.txt",
  "module-proxy": "proxy.txt",
  "module-reject": "reject.txt",
};

function findProxyGroup(config) {
  const groups = Array.isArray(config && config["proxy-groups"])
    ? config["proxy-groups"]
    : [];

  for (const name of PREFERRED_PROXY_GROUPS) {
    if (groups.some((group) => group && group.name === name)) return name;
  }

  const selectGroup = groups.find(
    (group) => group && group.type === "select" && group.name,
  );
  if (selectGroup) return selectGroup.name;

  const firstGroup = groups.find((group) => group && group.name);
  return firstGroup ? firstGroup.name : "GLOBAL";
}

function main(config, profileName) {
  const output = config && typeof config === "object" ? config : {};
  const providers =
    output["rule-providers"] && typeof output["rule-providers"] === "object"
      ? output["rule-providers"]
      : {};
  const proxyGroup = findProxyGroup(output);

  output["rule-providers"] = providers;
  const configuredProviders = [
    ...Object.entries(FIXED_PROVIDERS),
    ...Object.entries(MODULE_PROVIDERS),
  ];
  for (const [name, file] of configuredProviders) {
    providers[name] = {
      type: "http",
      behavior: "classical",
      format: "text",
      interval: 86400,
      url: `${BASE_URL}${file}`,
    };
  }

  const rules = Array.isArray(output.rules) ? output.rules : [];
  output.rules = [
    ...configuredProviders.map(([name]) => {
      const policy = name.endsWith("-direct")
        ? "DIRECT"
        : name.endsWith("-proxy")
          ? proxyGroup
          : "REJECT";
      return `RULE-SET,${name},${policy}`;
    }),
    ...rules,
  ];

  return output;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { main, findProxyGroup };
}
if (typeof globalThis !== "undefined") {
  globalThis.main = main;
  globalThis.findProxyGroup = findProxyGroup;
}
