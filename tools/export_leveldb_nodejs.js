#!/usr/bin/env node
/**
 * Export LevelDB to JSON using Node.js
 *
 * This is MUCH EASIER than Python for Windows users!
 * No C++ compiler needed, no build tools needed.
 *
 * Requirements:
 *   - Node.js (download from nodejs.org)
 *   - npm install level (automatic)
 *
 * Usage:
 *   node tools/export_leveldb_nodejs.js
 */

const fs = require('fs');
const path = require('path');

// Try to load level package
let ClassicLevel;
try {
    // Try classic-level first (better for reading existing LevelDB)
    try {
        ClassicLevel = require('classic-level').ClassicLevel;
    } catch (e1) {
        // Fallback to level package
        const level = require('level');
        ClassicLevel = level.Level || level;
    }
} catch (e) {
    console.error('\n❌ ERROR: "level" or "classic-level" package not installed\n');
    console.error('Please install one of them:');
    console.error('  npm install classic-level  (recommended)\n');
    console.error('  OR\n');
    console.error('  npm install level\n');
    process.exit(1);
}

/**
 * Export a LevelDB database to JSON
 */
async function exportDatabase(dbPath, outputPath, dbType) {
    console.log('\n' + '='.repeat(60));
    console.log(`Exporting ${dbType} database`);
    console.log('='.repeat(60));
    console.log(`Source: ${dbPath}`);
    console.log(`Output: ${outputPath}`);

    // Check if database exists
    if (!fs.existsSync(dbPath)) {
        console.log(`  ❌ Database not found at ${dbPath}`);
        return { success: false, error: 'Database not found' };
    }

    try {
        // Open LevelDB
        console.log('\nOpening database...');
        const db = new ClassicLevel(dbPath, {
            valueEncoding: 'utf8',
            createIfMissing: false
        });

        // Read all entries
        console.log('Reading fields...');
        const fields = {};
        let count = 0;

        for await (const [key, value] of db.iterator()) {
            try {
                const fieldData = JSON.parse(value);
                fields[key] = fieldData;
                count++;

                if (count % 100 === 0) {
                    process.stdout.write(`  Read ${count} fields...\r`);
                }
            } catch (e) {
                console.log(`\n  ⚠️  Error parsing field ${key}: ${e.message}`);
            }
        }

        console.log(`\n  ✅ Read ${count} fields`);

        // Close database
        await db.close();

        // Create export data
        const exportData = {
            metadata: {
                source: 'leveldb',
                db_type: dbType,
                exported_at: new Date().toISOString(),
                total_fields: count,
                source_path: dbPath,
                exported_by: 'export_leveldb_nodejs.js',
                exporter: 'Node.js + level package'
            },
            fields: fields
        };

        // Write JSON file
        console.log('\nWriting JSON file...');
        const outputDir = path.dirname(outputPath);
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir, { recursive: true });
        }

        fs.writeFileSync(outputPath, JSON.stringify(exportData, null, 2), 'utf8');

        const stats = fs.statSync(outputPath);
        const sizeMB = (stats.size / 1024 / 1024).toFixed(2);
        console.log(`  ✅ Exported to ${outputPath}`);
        console.log(`  File size: ${stats.size.toLocaleString()} bytes (${sizeMB} MB)`);

        return {
            success: true,
            fields_count: count,
            file_size: stats.size,
            output_path: outputPath
        };

    } catch (error) {
        console.log(`  ❌ Error: ${error.message}`);
        console.error(error);
        return { success: false, error: error.message };
    }
}

/**
 * Main function
 */
async function main() {
    console.log('\n' + '='.repeat(60));
    console.log('LEVELDB TO JSON EXPORTER (Node.js)');
    console.log('='.repeat(60));

    // Get VS Code extension path from environment or use default
    const vscodePath = process.env.FASTBUSINESS_VSCODE_DB_PATH ||
        'C:\\Users\\nguye\\.vscode\\extensions\\nguyen-hong-dat.fbo-autocomplete-0.0.40\\src\\Database';

    const outputDir = process.env.FASTBUSINESS_JSON_DB_PATH ||
        'database/json_exports';

    console.log(`\nVS Code extension path: ${vscodePath}`);
    console.log(`Output directory: ${outputDir}\n`);

    // Databases to export
    const databases = [
        { dir: 'Dir', file: 'dir.json', type: 'DIR' },
        { dir: 'Filter', file: 'filter.json', type: 'FILTER' },
        { dir: 'GridView', file: 'gridview.json', type: 'GRID_VIEW' },
        { dir: 'GridInput', file: 'gridinput.json', type: 'GRID_INPUT' },
    ];

    const results = [];

    // Export each database
    for (const db of databases) {
        const sourcePath = path.join(vscodePath, db.dir);
        const outputPath = path.join(outputDir, db.file);

        const result = await exportDatabase(sourcePath, outputPath, db.type);
        results.push({ type: db.type, result });
    }

    // Print summary
    console.log('\n' + '='.repeat(60));
    console.log('EXPORT SUMMARY');
    console.log('='.repeat(60));

    let totalFields = 0;
    let totalSize = 0;
    let successCount = 0;

    for (const { type, result } of results) {
        if (result.success) {
            successCount++;
            totalFields += result.fields_count;
            totalSize += result.file_size;
            const sizeMB = (result.file_size / 1024 / 1024).toFixed(2);
            console.log(`✅ ${type}: ${result.fields_count} fields, ${sizeMB} MB`);
        } else {
            console.log(`❌ ${type}: ${result.error}`);
        }
    }

    console.log(`\nTotal: ${successCount}/${results.length} databases exported`);
    console.log(`Total fields: ${totalFields.toLocaleString()}`);
    console.log(`Total size: ${(totalSize / 1024 / 1024).toFixed(2)} MB`);

    if (successCount > 0) {
        console.log('\n✅ Export completed successfully!');
        console.log('\nNext steps:');
        console.log(`  1. JSON files are ready at: ${path.resolve(outputDir)}`);
        console.log('  2. These files can be used with MCP server in JSON fallback mode');
        console.log('  3. Run: python -m fastbusiness_mcp.server');
        console.log('  4. Server will automatically detect and use JSON files');
    } else {
        console.log('\n❌ Export failed');
        console.log('\nTroubleshooting:');
        console.log('  - Check VS Code extension path is correct');
        console.log('  - Make sure LevelDB databases exist');
        console.log('  - Try setting FASTBUSINESS_VSCODE_DB_PATH environment variable');
    }
}

// Run main function
main().catch(error => {
    console.error('\n❌ Fatal error:', error);
    process.exit(1);
});
