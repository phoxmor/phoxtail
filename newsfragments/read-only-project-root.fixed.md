The MCP server and API token checks no longer fail in production images that
carry no `.phoxtail` folder, such as those built with the new `.dockerignore`.
Importing the MCP server tried to create `.phoxtail/mcp/uploads` under `/app`,
which the app user cannot write there, and every API token check imports it.
The screenshot tools now still return the image when they cannot also save a
copy under `.phoxtail/vision/`.
