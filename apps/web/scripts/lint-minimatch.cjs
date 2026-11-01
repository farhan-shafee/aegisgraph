// The preload imports this file before registering its resolution hook.
// Resolve first, then require the absolute path, so Node does not cache a bare
// "minimatch" lookup that would bypass the subsequent hook in this directory.
// eslint-disable-next-line @typescript-eslint/no-require-imports -- This facade must provide CommonJS exports to legacy plugins.
const core = require(require.resolve("minimatch"));

module.exports = (path, pattern, options) =>
  core.minimatch(path, pattern, options);

// Explicit assignments expose named imports to Node's CommonJS module lexer.
module.exports.minimatch = core.minimatch;
module.exports.Minimatch = core.Minimatch;
module.exports.sep = core.sep;
module.exports.GLOBSTAR = core.GLOBSTAR;
module.exports.filter = core.filter;
module.exports.defaults = core.defaults;
module.exports.braceExpand = core.braceExpand;
module.exports.match = core.match;
module.exports.escape = core.escape;
module.exports.unescape = core.unescape;

// eslint-plugin-import/no-internal-modules only uses makeRe(...).test(path).
// Provide that interface with the patched matcher, without generating a RegExp.
// This is a test object, not a general replacement for the removed RegExp API.
module.exports.makeRe = (pattern, options) => {
  const matcher = new core.Minimatch(pattern, options);
  return { test: (path) => matcher.match(path) };
};
