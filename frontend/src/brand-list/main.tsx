// The island entry Django's page loads. It imports no CSS: the page links
// the theme stylesheet (ADR 0023).
import { mountBrandList } from './mount';

const root = document.getElementById('brand-list');
if (!root) throw new Error('No #brand-list element on this page.');
mountBrandList(root);
