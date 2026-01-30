# Working with documentation

To update the documentation on any of the sections just add a new markdown file to the designated subfolder below :

```
├─concepts
├─tutorials
├─how-to
│ └─troubleshooting
└─reference
  ├─architecture
  ├─decisions
  └─faq
```

:::note Templates

Each folder contains templates that can be used as quickstarts. Those are named `<template name>.tpml`.

:::

See [Diataxis documentation](../reference/diataxis-documentation.md) for more information on diátaxis.

## Manage Docs Versions

Docusaurus can manage multiple versions of the docs.

### Create a docs version

Release a version 1.0 of your project:

```bash
npm run docusaurus docs:version 1.0
```

The `docs` folder is copied into `versioned_docs/version-1.0` and `versions.json` is created.

Your docs now have 2 versions:

- `1.0` at `http://localhost:3000/docs/` for the version 1.0 docs
- `current` at `http://localhost:3000/docs/next/` for the **upcoming, unreleased docs**

### Add a Version Dropdown

To navigate seamlessly across versions, add a version dropdown.

Modify the `docusaurus.config.js` file:

```js title="docusaurus.config.js"
export default {
  themeConfig: {
    navbar: {
      items: [
        // highlight-start
        {
          type: 'docsVersionDropdown',
        },
        // highlight-end
      ],
    },
  },
};
```

The docs version dropdown appears in the navbar.

## Update an existing version

It is possible to edit versioned docs in their respective folder:

- `versioned_docs/version-1.0/hello.md` updates `http://localhost:3000/docs/hello`
- `docs/hello.md` updates `http://localhost:3000/docs/next/hello`
