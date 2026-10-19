import { fileURLToPath } from 'node:url';
import { includeIgnoreFile } from '@eslint/compat';
import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import svelte from 'eslint-plugin-svelte';
import { defineConfig } from 'eslint/config';
import globals from 'globals';
import ts from 'typescript-eslint';

const gitignorePath = fileURLToPath(new URL('./.gitignore', import.meta.url));

export default defineConfig(
	includeIgnoreFile(gitignorePath),
	js.configs.recommended,
	ts.configs.recommended,
	svelte.configs.recommended,
	prettier,
	svelte.configs.prettier,
	{
		languageOptions: {
			globals: { ...globals.browser, ...globals.node, ...globals.webextensions }
		},
		rules: {
			// TypeScript already checks for undefined identifiers.
			'no-undef': 'off',
			// Icons only through the web app's Icon.svelte (AGENTS.md, hard rule 4).
			'no-restricted-imports': [
				'error',
				{
					patterns: [
						{
							group: ['@lucide/svelte', '@lucide/svelte/*'],
							message: 'Use @web/components/ui/Icon.svelte instead of importing icons directly.'
						}
					]
				}
			]
		}
	},
	{
		files: ['**/*.svelte', '**/*.svelte.ts'],
		languageOptions: {
			parserOptions: {
				projectService: true,
				extraFileExtensions: ['.svelte'],
				parser: ts.parser
			}
		}
	}
);
