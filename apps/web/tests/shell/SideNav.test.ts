import { act, render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SideNav from '#lib/components/shell/SideNav.svelte';
import { setViewportWidth } from '../media';

const location = vi.hoisted(() => ({ pathname: '/app/profiles' }));

vi.mock('$app/state', () => ({
	page: {
		get url() {
			return new URL(`http://localhost${location.pathname}`);
		}
	}
}));
vi.mock('$app/paths', () => ({
	resolve: (path: string) => path,
	asset: (path: string) => path
}));

const mocks = vi.hoisted(() => ({ goto: vi.fn(), session: null as never }));
vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('#lib/auth/session.svelte.ts', async () => {
	const { sessionMock } = await import('../routes/session-mock');
	mocks.session = sessionMock() as never;
	return { session: mocks.session };
});

function session() {
	return mocks.session as unknown as ReturnType<
		typeof import('../routes/session-mock').sessionMock
	>;
}

function nav() {
	return screen.getByRole('navigation', { name: 'Main' });
}

describe('SideNav', () => {
	beforeEach(() => {
		localStorage.clear();
		setViewportWidth(1280);
		location.pathname = '/app/profiles';
	});
	afterEach(() => {
		vi.restoreAllMocks();
	});

	it('links the brand to the landing page', () => {
		render(SideNav);

		expect(within(nav()).getByRole('link', { name: 'Chameleon vitae' })).toHaveAttribute(
			'href',
			'/'
		);
	});

	it('lists the six sections in order with their routes', () => {
		render(SideNav);
		const links = within(within(nav()).getByRole('list')).getAllByRole('link');
		expect(links.map((link) => [link.textContent?.trim(), link.getAttribute('href')])).toEqual([
			['Documents', '/app/documents'],
			['Profiles', '/app/profiles'],
			['Tailor', '/app/tailor'],
			['Templates', '/app/templates'],
			['Settings', '/app/settings']
		]);
	});

	it('marks the current section, including nested routes', () => {
		location.pathname = '/app/documents/123';
		render(SideNav);
		const active = screen.getByRole('link', { name: 'Documents' });
		expect(active).toHaveAttribute('aria-current', 'page');
		expect(active).toHaveClass('bg-muted', 'font-medium', 'text-fg');
		expect(active.querySelector('.bg-accent')).not.toBeNull();
		expect(screen.getByRole('link', { name: 'Profiles' })).not.toHaveAttribute('aria-current');
	});

	it('collapses to a 56px icon rail and back, remembering the choice', async () => {
		const user = userEvent.setup();
		render(SideNav);
		expect(nav()).toHaveClass('w-60');
		await user.click(screen.getByRole('button', { name: 'Collapse side nav' }));
		expect(nav()).toHaveClass('w-14');
		expect(nav()).toHaveAttribute('data-collapsed', 'true');
		expect(localStorage.getItem('vitae.sidenav.collapsed')).toBe('true');
		// Labels stay available to assistive tech in the rail.
		expect(screen.getByRole('link', { name: 'Settings' })).toBeInTheDocument();
		await user.click(screen.getByRole('button', { name: 'Expand side nav' }));
		expect(nav()).toHaveClass('w-60');
		expect(localStorage.getItem('vitae.sidenav.collapsed')).toBe('false');
	});

	it('starts collapsed when the user collapsed it before', () => {
		localStorage.setItem('vitae.sidenav.collapsed', 'true');
		render(SideNav);
		expect(nav()).toHaveClass('w-14');
	});

	it('shows labels as tooltips in the rail', async () => {
		vi.useFakeTimers();
		try {
			const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
			localStorage.setItem('vitae.sidenav.collapsed', 'true');
			render(SideNav);
			await user.hover(screen.getByRole('link', { name: 'Tailor' }));
			await act(() => vi.advanceTimersByTime(400));
			expect(
				screen.getAllByText('Tailor').some((el) => el.getAttribute('data-state') === 'open')
			).toBe(true);
		} finally {
			vi.useRealTimers();
		}
	});

	it('shows the logo beside the name, and alone in the rail', async () => {
		render(SideNav);
		expect(within(nav()).getByText('Chameleon vitae').querySelector('img')).toHaveAttribute(
			'src',
			'logo.svg'
		);
		// Under 1024px the rail has no toggle; the logo stands in for the name.
		await act(() => setViewportWidth(768));
		expect(within(nav()).getByRole('img', { name: 'Chameleon vitae' })).toBeVisible();
		await act(() => setViewportWidth(1280));
	});

	it('is always the icon rail under 1024px, without a toggle', async () => {
		render(SideNav);
		expect(nav()).toHaveClass('w-60');
		await act(() => setViewportWidth(768));
		expect(nav()).toHaveClass('w-14');
		expect(screen.queryByRole('button', { name: /side nav/ })).toBeNull();
		await act(() => setViewportWidth(1280));
		expect(nav()).toHaveClass('w-60');
	});

	it('still works when local storage is unavailable', async () => {
		vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
			throw new Error('blocked');
		});
		vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
			throw new Error('blocked');
		});
		render(SideNav);
		expect(nav()).toHaveClass('w-60');
		await userEvent.click(screen.getByRole('button', { name: 'Collapse side nav' }));
		expect(nav()).toHaveClass('w-14');
	});

	it('shows the plan but not the AI usage, which lives in Settings', async () => {
		session().me = { plan: 'free', email: 'ada@example.com', display_name: null };
		session().usage = { plan: 'pro', ai_runs: { used: 3, limit: 150, message: null } };
		render(SideNav);

		expect(within(nav()).getByText('Pro')).toBeVisible();
		expect(within(nav()).queryByText(/AI|150|%/)).toBeNull();
		session().usage = null;
	});

	it('shows the account with its plan, and signs out from the account menu', async () => {
		session().email = 'ada@example.com';
		session().me = { plan: 'free', email: 'ada@example.com', display_name: null };
		const user = userEvent.setup();
		render(SideNav);

		expect(within(nav()).getByText('ada@example.com')).toBeVisible();
		expect(within(nav()).getByText('Free')).toBeVisible();
		expect(session().loadUsage).toHaveBeenCalled();

		await user.click(within(nav()).getByRole('button', { name: 'Account' }));
		await user.click(screen.getByRole('menuitem', { name: 'Sign out' }));
		expect(session().signOut).toHaveBeenCalledOnce();

		await user.click(within(nav()).getByRole('button', { name: 'Account' }));
		await user.click(screen.getByRole('menuitem', { name: 'Settings' }));
		expect(mocks.goto).toHaveBeenCalledWith('/app/settings');
	});
});
