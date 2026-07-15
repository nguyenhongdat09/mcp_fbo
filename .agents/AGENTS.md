# Agent Rules

## XML File Handling Constraint
- **CRITICAL RULE**: Under no circumstances should the agent automatically create or generate missing XML files or metadata/controllers/views/queries files in the FBO project.
- If a required XML file (or any other project source file) is found to be missing, you **MUST** report the missing file to the user immediately and ask for their instructions. **DO NOT** attempt to create or generate the file yourself.