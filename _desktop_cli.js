TWARE.
import { basename, delimiter, dirname, join, resolve } from "node:path";
import { runCli } from "@deepseek-ai/dsh/lib/bin.js";
//#region \0rolldown/runtime.js
var __defProp = Object.defineProperty;
var __esmMin = (fn, res) => () => (fn && (res = fn(fn = 0)), res);
var __exportAll = (all, no_symbols) => {
	let target = {};
	for (var name in all) __defProp(target, name, {
		get: all[name],
		enumerable: true
	});
	if (!no_symbols) __defProp(target, Symbol.toStringTag, { value: "Module" });
	return target;
};
//#endregion
//#region lib/types/windows-cli-signals.js
var windows_cli_signals_exports = /* @__PURE__ */ __exportAll({ installWindowsCliSignals: () => installWindowsCliSignals });
/** Deliver console interrupts to CLI listeners in Electron's Windows Node mode. */
/**
* Register the CLI process's Windows console handler.
* Koffi queues callbacks from the console thread onto the JavaScript thread.
* The registration lasts until process exit; unknown events retain native handling.
* @returns Completion once the console handler is registered.
*/
async function installWindowsCliSignals() {
	const { default: koffi } = await import("koffi");
	const kernel = koffi.load("kernel32.dll");
	const type = koffi.proto("int __stdcall DshCliConsoleHandler(uint32_t event)");
	const handler = koffi.register((event) => {
		if (event === 0) return Number(process.emit("SIGINT"));
		if (event === 1) return Number(process.emit("SIGBREAK"));
		return 0;
	}, koffi.pointer(type));
	if (!kernel.func("int __stdcall SetConsoleCtrlHandler(DshCliConsoleHandler *handler, int add)")(handler, 1)) {
		koffi.unregister(handler);
		throw new Error("desktop CLI: cannot register the Windows console handler");
	}
}
var init_windows_cli_signals = __esmMin((() => {}));
//#endregion
//#region lib/types/cli.js
/** Public dsh commands using the immutable runtime carried by the Desktop installation. */
/**
* Locate the archive containing a packaged runtime.
* @param runtimeDir - Prepared or ASAR-contained runtime directory.
* @returns Parent archive path, or undefined for a prepared directory.
*/
function runtimeArchivePath(runtimeDir) {
	const parent = dirname(runtimeDir);
	return basename(parent) === "app.asar" ? parent : void 0;
}
/**
* Run the ordinary CLI with Desktop's bundled package manager and reserved-profile plugin access.
* @param supportDir - Physical Desktop runtime directory containing the primary-runtime payload and Node launchers.
* @returns Completion of the selected CLI command; profile plugins own their process lifetime.
*/
async function runDesktopCli(supportDir) {
	await runCli({
		manageDesktopProfile: true,
		packageManager: {
			command: process.execPath,
			args: ["--expose-internals", join(supportDir, "primary-runtime", "dependencies", "pnpm", "bin", "pnpm.mjs")],
			env: {
				ELECTRON_RUN_AS_NODE: "1",
				DSH_DESKTOP_NODE_EXECUTABLE: process.execPath,
				PATH: `${join(supportDir, "bin")}${delimiter}${process.env.PATH ?? ""}`
			}
		}
	});
}
if (import.meta.main) {
	if (process.platform === "win32") {
		const { installWindowsCliSignals } = await Promise.resolve().then(() => (init_windows_cli_signals(), windows_cli_signals_exports));
		await installWindowsCliSignals();
	}
	const runtimeDir = resolve(import.meta.dirname, "../../../..");
	await runDesktopCli(join(dirname(runtimeArchivePath(runtimeDir) ?? runtimeDir), "runtime"));
}
//#endregion
export { runDesktopCli, runtimeArchiveP