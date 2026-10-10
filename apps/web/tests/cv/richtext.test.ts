import { describe, expect, it } from 'vitest';
import { parseRich, type Span } from '#lib/cv/richtext.ts';

/** The cases of packages/cvcore/tests/test_richtext.py: "" literal, "b" bold, "p" placeholder. */
function spans(...parts: [string, string][]): Span[] {
	return parts.map(([t, flags]) => ({ t, b: flags.includes('b'), p: flags.includes('p') }));
}

describe('parseRich', () => {
	it.each<[string, Span[]]>([
		['', []],
		['Plain text', spans(['Plain text', ''])],
		['Cut costs by **40%**', spans(['Cut costs by ', ''], ['40%', 'b'])],
		[
			'Served [[number of users]] users',
			spans(['Served ', ''], ['number of users', 'p'], [' users', ''])
		],
		['**[[check this number: 40%]]**', spans(['check this number: 40%', 'bp'])],
		[
			'**up [[n]] times** faster',
			spans(['up ', 'b'], ['n', 'bp'], [' times', 'b'], [' faster', ''])
		],
		['[[**literal** inside]]', spans(['**literal** inside', 'p'])],
		['a ** b', spans(['a ** b', ''])],
		['****', spans(['****', ''])],
		['[[]]', spans(['[[]]', ''])],
		['**a**b**', spans(['a', 'b'], ['b**', ''])],
		['**a****b**', spans(['a', 'b'], ['**b**', ''])],
		['**a*****b**', spans(['a', 'b'], ['*', ''], ['b', 'b'])],
		['***a**', spans(['*a', 'b'])],
		['**a [[b** c]]', spans(['a [[b', 'b'], [' c]]', ''])],
		['[[a **b]] c**', spans(['a **b', 'p'], [' c**', ''])],
		['[[a]][[b]]', spans(['a', 'p'], ['b', 'p'])]
	])('parses %j', (text, expected) => {
		expect(parseRich(text)).toEqual(expected);
	});
});
