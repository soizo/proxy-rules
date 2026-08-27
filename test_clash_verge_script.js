const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const scriptPath = path.join(__dirname, "clash-verge-script.js");
const code = fs.readFileSync(scriptPath, "utf8");
const context = {
  console,
  module: { exports: {} },
  exports: {},
  require,
};

vm.createContext(context);
vm.runInContext(code, context, { filename: scriptPath });

const main = context.module.exports.main || context.main;
const findProxyGroup =
  context.module.exports.findProxyGroup || context.findProxyGroup;
const plain = (value) => JSON.parse(JSON.stringify(value));

assert.strictEqual(typeof main, "function");
assert.strictEqual(typeof findProxyGroup, "function");

const config = {
  rules: ["SUBSCRIPTION-RULE"],
  "rule-providers": {
    existing: {
      type: "http",
      behavior: "classical",
      format: "text",
      interval: 3600,
    },
  },
  "proxy-groups": [
    { name: "节点选择", type: "select", proxies: ["DIRECT"] },
    { name: "Auto", type: "url-test", proxies: ["节点选择"] },
  ],
};

assert.strictEqual(findProxyGroup(config), "节点选择");

const output = main(structuredClone(config), "profile");

assert.deepStrictEqual(
  plain(output["rule-providers"].existing),
  config["rule-providers"].existing,
);
assert.deepStrictEqual(plain(output["rule-providers"]["fixed-direct"]), {
  type: "http",
  behavior: "classical",
  format: "text",
  interval: 86400,
  url: "https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/fixed-direct.txt",
});
assert.deepStrictEqual(plain(output["rule-providers"]["fixed-proxy"]), {
  type: "http",
  behavior: "classical",
  format: "text",
  interval: 86400,
  url: "https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/fixed-proxy.txt",
});
assert.strictEqual(output["rule-providers"]["fixed-reject"], undefined);
assert.deepStrictEqual(plain(output["rule-providers"]["module-direct"]), {
  type: "http",
  behavior: "classical",
  format: "text",
  interval: 86400,
  url: "https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/direct.txt",
});
assert.deepStrictEqual(plain(output["rule-providers"]["module-proxy"]), {
  type: "http",
  behavior: "classical",
  format: "text",
  interval: 86400,
  url: "https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/proxy.txt",
});
assert.deepStrictEqual(plain(output["rule-providers"]["module-reject"]), {
  type: "http",
  behavior: "classical",
  format: "text",
  interval: 86400,
  url: "https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/reject.txt",
});
assert.deepStrictEqual(plain(output.rules.slice(0, 5)), [
  "RULE-SET,fixed-direct,DIRECT",
  "RULE-SET,fixed-proxy,节点选择",
  "RULE-SET,module-direct,DIRECT",
  "RULE-SET,module-proxy,节点选择",
  "RULE-SET,module-reject,REJECT",
]);
assert.deepStrictEqual(plain(output.rules.slice(5)), ["SUBSCRIPTION-RULE"]);

const empty = main({}, "profile");
assert.deepStrictEqual(plain(empty["rule-providers"]), {
  "fixed-direct": {
    type: "http",
    behavior: "classical",
    format: "text",
    interval: 86400,
    url: "https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/fixed-direct.txt",
  },
  "fixed-proxy": {
    type: "http",
    behavior: "classical",
    format: "text",
    interval: 86400,
    url: "https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/fixed-proxy.txt",
  },
  "module-direct": {
    type: "http",
    behavior: "classical",
    format: "text",
    interval: 86400,
    url: "https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/direct.txt",
  },
  "module-proxy": {
    type: "http",
    behavior: "classical",
    format: "text",
    interval: 86400,
    url: "https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/proxy.txt",
  },
  "module-reject": {
    type: "http",
    behavior: "classical",
    format: "text",
    interval: 86400,
    url: "https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/reject.txt",
  },
});
assert.deepStrictEqual(plain(empty.rules), [
  "RULE-SET,fixed-direct,DIRECT",
  "RULE-SET,fixed-proxy,GLOBAL",
  "RULE-SET,module-direct,DIRECT",
  "RULE-SET,module-proxy,GLOBAL",
  "RULE-SET,module-reject,REJECT",
]);

console.log("clash-verge-script self-check passed");
