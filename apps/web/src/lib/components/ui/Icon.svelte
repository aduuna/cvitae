<script lang="ts">
	import { icons, type IconName } from './icons';

	interface Props {
		name: IconName;
		/** 16px everywhere; 20px only in empty states. */
		size?: 16 | 20;
		/** Rotate continuously, for the loading spinner. */
		spin?: boolean;
	}

	let { name, size = 16, spin = false }: Props = $props();

	const Glyph = $derived(icons[name]);
</script>

<Glyph
	{size}
	strokeWidth={1.5}
	color="currentColor"
	aria-hidden="true"
	focusable="false"
	class={['shrink-0', spin && 'animate-spin']}
	data-icon={name}
/>
