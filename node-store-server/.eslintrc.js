// eslint.config.js
import { defineConfig } from "eslint/config";

export default defineConfig([
	{
		rules: {
            tsconfigRootDir: __dirname,
			semi: "error",
			"prefer-const": "error",
		},
	},
]);