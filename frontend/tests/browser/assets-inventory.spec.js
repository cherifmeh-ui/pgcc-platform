import { test, expect } from '@playwright/test';

const assetOne = {
  id: '00000000-0000-0000-0000-000000000101',
  reference: 'AST-001',
  name: 'Serveur de production',
  asset_type: 'hardware',
  criticality: 'Critique',
  lifecycle_status: 'Actif',
  owner: 'Direction IT',
  direction: 'DI',
  location: 'Datacenter',
  hostname: 'srv-prod-01',
  retired_at: null,
};

const assetTwo = {
  id: '00000000-0000-0000-0000-000000000102',
  reference: 'AST-002',
  name: 'Application métier',
  asset_type: 'application',
  criticality: 'Élevée',
  lifecycle_status: 'Actif',
  owner: 'Métiers',
  direction: 'Exploitation',
  location: 'Tunis',
  hostname: null,
  retired_at: null,
};

const quality = {
  total_active: 2,
  missing_owner: 0,
  missing_classification: 0,
  missing_inventory_date: 0,
  missing_criticality: 0,
  missing_direction: 0,
  support_overdue: 0,
  support_ending_90_days: 0,
  completeness_percent: 100,
};

const graph = {
  nodes: [
    { id: assetOne.id, reference: assetOne.reference, name: assetOne.name, asset_type: assetOne.asset_type, criticality: assetOne.criticality, direction: assetOne.direction, lifecycle_status: 'Actif', owner: assetOne.owner, location: assetOne.location },
    { id: assetTwo.id, reference: assetTwo.reference, name: assetTwo.name, asset_type: assetTwo.asset_type, criticality: assetTwo.criticality, direction: assetTwo.direction, lifecycle_status: 'Actif', owner: assetTwo.owner, location: assetTwo.location },
  ],
  edges: [
    { id: '00000000-0000-0000-0000-000000000201', source: assetTwo.id, target: assetOne.id, relationship_type: 'depends_on', description: 'Application hébergée sur le serveur' },
  ],
  node_count: 2,
  edge_count: 1,
};

async function mockPgccApi(page, role = 'admin') {
  const permissions = {
    dashboard: ['read'],
    assets: role === 'viewer' ? [] : ['read', ...(role === 'admin' ? ['create', 'update', 'delete'] : []), 'export'],
    apps: ['read'],
    risks: ['read'],
    suppliers: ['read_assets'],
  };

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace('/api/v1', '');

    if (path === '/auth/refresh' && request.method() === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'pgcc-assets-e2e-access-token',
          user: {
            id: '00000000-0000-0000-0000-000000000301',
            email: 'assets-e2e@example.test',
            role,
            is_active: true,
            must_change_password: false,
            mfa_enabled: true,
          },
        }),
      });
    }

    if (path === '/me/permissions') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ permissions }),
      });
    }

    if (path === '/assets/page') {
      const query = url.searchParams;
      const selected = query.get('q')?.includes('AST-002') || query.get('page') === '2'
        ? [assetTwo]
        : [assetOne];
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: selected,
          total: 2,
          page: Number(query.get('page') || 1),
          page_size: Number(query.get('page_size') || 25),
          pages: 2,
        }),
      });
    }

    if (path === '/assets/quality') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(quality) });
    }

    if (path === '/apps/') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    }

    if (path === '/assets/graph') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(graph) });
    }

    if (path === '/assets/import/preview' && request.method() === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          rows_parsed: 1,
          errors: [],
          preview: [{
            row: 2,
            data: {
              reference: 'AST-CSV-001',
              name: 'Actif importé',
              asset_type: 'hardware',
              criticality: 'Moyenne',
            },
          }],
          can_import: true,
        }),
      });
    }

    if (path === '/assets/import/confirm' && request.method() === 'POST') {
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ imported: 1, message: '1 actifs importés avec succès.' }),
      });
    }

    return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
}

test('admin navigates inventory pages, applies filters and opens dependency graph', async ({ page }) => {
  await mockPgccApi(page, 'admin');
  await page.goto('/assets');

  await expect(page.getByRole('heading', { name: 'Cartographie des actifs' })).toBeVisible();
  await expect(page.getByText('AST-001')).toBeVisible();

  await page.getByRole('button', { name: 'Suivant' }).click();
  await expect(page.getByText('AST-002')).toBeVisible();

  await page.getByPlaceholder('Rechercher référence, nom, hostname…').fill('AST-002');
  await expect(page.getByText('AST-002')).toBeVisible();

  await page.getByRole('button', { name: 'Graphe des dépendances' }).click();
  await expect(page.getByText('2 actifs · 1 relations')).toBeVisible();
  await expect(page.locator('.graph-list').getByText('AST-001 — Serveur de production')).toBeVisible();
  await expect(page.locator('.graph-list').getByText('AST-002 — Application métier')).toBeVisible();
});

test('auditor can read and export inventory but cannot mutate assets', async ({ page }) => {
  await mockPgccApi(page, 'auditor');
  await page.goto('/assets');

  await expect(page.getByRole('heading', { name: 'Cartographie des actifs' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Exporter CSV' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Importer CSV' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Nouvel actif/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Modifier' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Retirer' })).toHaveCount(0);
});

test('viewer without assets scope is redirected away from Cartography', async ({ page }) => {
  await mockPgccApi(page, 'viewer');
  await page.goto('/assets');

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole('link', { name: 'Cartographie' })).toHaveCount(0);
});


test('admin creates and updates an asset, then exports the filtered inventory', async ({ page }) => {
  await mockPgccApi(page, 'admin');
  await page.goto('/assets');

  const createRequest = page.waitForRequest((request) =>
    request.method() === 'POST' && new URL(request.url()).pathname.endsWith('/assets/')
  );
  await page.getByRole('button', { name: /Nouvel actif/ }).click();
  await page.getByLabel('Référence *').fill('AST-NEW-001');
  await page.getByLabel('Nom *').fill('Nouvel actif de test');
  await page.locator('form.modal').getByRole('button', { name: 'Enregistrer' }).click();
  const created = await createRequest;
  expect(created.postDataJSON().reference).toBe('AST-NEW-001');
  expect(created.postDataJSON().name).toBe('Nouvel actif de test');
  await expect(page.locator('form.modal')).toHaveCount(0);

  const updateRequest = page.waitForRequest((request) =>
    request.method() === 'PATCH' && new URL(request.url()).pathname.endsWith('/' + assetOne.id)
  );
  await page.getByRole('button', { name: 'Modifier' }).first().click();
  await page.getByLabel('Nom *').fill('Serveur de production renommé');
  await page.locator('form.modal').getByRole('button', { name: 'Enregistrer' }).click();
  const updated = await updateRequest;
  expect(updated.postDataJSON().name).toBe('Serveur de production renommé');
  await expect(page.locator('form.modal')).toHaveCount(0);

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Exporter CSV' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('pgcc_assets_inventory.csv');
});

test('admin previews and confirms a CSV import without bypassing the preview step', async ({ page }) => {
  await mockPgccApi(page, 'admin');
  page.on('dialog', (dialog) => dialog.accept());
  await page.goto('/assets');

  await page.getByRole('button', { name: 'Importer CSV' }).click();
  const previewRequest = page.waitForRequest((request) =>
    request.method() === 'POST' && new URL(request.url()).pathname.endsWith('/assets/import/preview')
  );
  await page.locator('input[type="file"]').setInputFiles({
    name: 'assets.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('reference,name,asset_type\nAST-CSV-001,Actif importé,hardware\n'),
  });
  await previewRequest;
  await expect(page.getByText('AST-CSV-001')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Confirmer l’import' })).toBeEnabled();

  const confirmRequest = page.waitForRequest((request) =>
    request.method() === 'POST' && new URL(request.url()).pathname.endsWith('/assets/import/confirm')
  );
  await page.getByRole('button', { name: 'Confirmer l’import' }).click();
  await confirmRequest;
  await expect(page.getByRole('heading', { name: 'Cartographie des actifs' })).toBeVisible();
});
