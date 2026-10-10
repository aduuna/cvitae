// The only module that imports from @lucide/svelte. Components use Icon.svelte with a name from here.
import Check from '@lucide/svelte/icons/check';
import ChevronDown from '@lucide/svelte/icons/chevron-down';
import CircleAlert from '@lucide/svelte/icons/circle-alert';
import Code from '@lucide/svelte/icons/code';
import Copy from '@lucide/svelte/icons/copy';
import Download from '@lucide/svelte/icons/download';
import Ellipsis from '@lucide/svelte/icons/ellipsis';
import File from '@lucide/svelte/icons/file';
import FileText from '@lucide/svelte/icons/file-text';
import GripVertical from '@lucide/svelte/icons/grip-vertical';
import LayoutTemplate from '@lucide/svelte/icons/layout-template';
import ListTree from '@lucide/svelte/icons/list-tree';
import LoaderCircle from '@lucide/svelte/icons/loader-circle';
import PanelLeftClose from '@lucide/svelte/icons/panel-left-close';
import PanelLeftOpen from '@lucide/svelte/icons/panel-left-open';
import Plus from '@lucide/svelte/icons/plus';
import RotateCcwClock from '@lucide/svelte/icons/rotate-ccw-clock';
import Settings from '@lucide/svelte/icons/settings';
import Target from '@lucide/svelte/icons/target';
import Trash from '@lucide/svelte/icons/trash';
import Upload from '@lucide/svelte/icons/upload';
import UserRound from '@lucide/svelte/icons/user-round';
import X from '@lucide/svelte/icons/x';

/**
 * Icons by purpose (docs/DESIGN.md, Icons). Lucide 1.x renamed Trash2 to `trash` and History to
 * `rotate-ccw-clock`; the glyphs are the same.
 */
export const icons = {
	documents: FileText,
	profiles: UserRound,
	import: Upload,
	tailor: Target,
	templates: LayoutTemplate,
	settings: Settings,
	new: Plus,
	duplicate: Copy,
	delete: Trash,
	download: Download,
	versions: RotateCcwClock,
	drag: GripVertical,
	'nav-collapse': PanelLeftClose,
	'nav-expand': PanelLeftOpen,
	'placeholder-warning': CircleAlert,
	code: Code,
	form: ListTree,
	close: X,
	'chevron-down': ChevronDown,
	check: Check,
	loading: LoaderCircle,
	more: Ellipsis,
	file: File
} as const;

export type IconName = keyof typeof icons;
