const vscode = require('vscode');
const path = require('path');
const fs = require('fs');
const ana = require('./AnalystXMLFile');
var level = require('level-rocksdb');
var Constant = require('../constant') 

class RenderXMLToDB extends ana {
    constructor() {
        super()
        this.excludeHrFile = true; //Khong lay file HR
        this.dbRender = new DatabaseRender();
    }

    run(context) {
        this.constant = new Constant(context)
        const render = vscode.commands.registerCommand('fbo-autocomplete.renderXmlTodDB', async () => {
            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: "Rendering",
                cancellable: false
            }, async (progress) => {
                var val = await this.AnalystField();
                // await this.dbRender.deleteDatabase()
                await this.dbRender.run(val);
               // await this.dbRender.saveToAutoCompleteJson();
            });
        });

        context.subscriptions.push(render);
    } 

    getPathDirGridFiler() {
        var pathFile = vscode.window.activeTextEditor.document.uri.fsPath;
        var idx = pathFile.indexOf('\\Controllers\\');

        if (idx === -1)
            return []

        var pathToControllers = pathFile.substring(0, idx + '\\Controllers\\'.length);
        var folder = ['Filter', 'Grid', 'Dir']
        return folder.map((item) => {
            return [item, path.resolve(path.join(pathToControllers, item))];
        })
    }

    getFileInFolder(folder) {
        var files = fs.readdirSync(folder);
        // Lọc chỉ file (nếu cần)
        files = files.filter(file => {
            var fullPath = path.join(folder, file);
            return fs.statSync(fullPath).isFile();
        });
        var fileMap = {};
        for (var file of files) {
            var ext = path.extname(file).toLowerCase(); // ".xml" hoặc ".f"
            var name = path.basename(file, ext);        // tên không có đuôi
            if (this.excludeHrFile && /^hr/i.test(name)) continue;
            var fullPath = path.join(folder, file);
            // Ưu tiên .xml nếu trùng tên
            if (ext === '.xml') {
                fileMap[name] = fullPath;
            } else if (ext === '.f') {
                if (!fileMap[name]) {
                    fileMap[name] = fullPath;
                }
            }
        }
        // Trả ra danh sách file đã chọn
        return Object.values(fileMap);
    }

    getPathFolders() {
        var folderPaths = this.getPathDirGridFiler();
        return folderPaths.map(([key, value]) => [key, this.getFileInFolder(value)])
    }


    async AnalystFile() {
        var paths = this.getPathFolders();
        var funcHandle = {
            'Dir': this.filterDirField.bind(this),
            'Filter': this.filterDirField.bind(this),
            'Grid': this.gridField.bind(this),
        }
        //Debugger
        // paths = paths.filter(([key, value]) => key == 'Dir');

        var fields_of_folders = await Promise.all(
            paths.map(async ([folder, paths]) => {
                var func = funcHandle[folder];
                return [folder, await func(paths)]
            })
        );
        return fields_of_folders
    }

    async AnalystField() {
        var fields = await this.AnalystFile();
        return fields.map(([folder, fields_item]) => {
            return fields_item.flatMap(Object.entries).map(([id, value]) => {
                return this.ClassificationField(folder, value.key, value.value);
            })
        })
    }

    ClassificationField(folder, field, value) {
        var hasAutoComplete = /style\s*=\s*"AutoComplete"/.test(value);
        var hasLookup = /style\s*=\s*"Lookup"/.test(value);
        var hasExternal = /external\s*=\s*"true"/.test(value);
        var hasGridView = /allow(Sorting|Filter)\s*=\s*"true"/.test(value);
        var folder_sign;

        var folder_sign =
            (folder === 'Filter' || folder === 'Dir') ? folder :
                (folder === 'Grid' && hasGridView) ? 'GridView' :
                    (folder === 'Grid') ? 'GridInput' :
                        undefined;
        //field_value = [field, value, controller]
        value = this.removeUnusedTag(value);
        return [
            folder_sign,
            hasAutoComplete ? this.lookupAutocompletField(field, value, 'at')
                : hasLookup ? this.lookupAutocompletField(field, value, 'lk')
                    : hasExternal ? this.externalField(field, value)
                        : [field, value, '']
        ]

    }

    removeElementNotExternal(value) {
        const attrs = [
            "clientDefault", "defaultValue", "readOnly", "disabled"
        ];
        for (var attr of attrs) {
            value = value.replace(new RegExp(`\\s*${attr}="[^"]*"`, 'g'), '');
        }
        return value;
    }

    lookupAutocompletField(field, value, prefix) {
        var controller = value.match(/controller\s*=\s*"([^"]+)"/);
        value = this.removeElementNotExternal(value);
        return [field + prefix, value, controller === null ? '' : controller[1]]
    }

    externalField(field, value) {
        return [field + 'ex', value, '']
    }

    removeElement(value) {
        const attrs = [
            "allowNulls", "isPrimaryKey", "hidden", "categoryIndex",
            "filterSource", "allowContain", "onDemand",
            "aliasName", "operation"
        ];
        for (var attr of attrs) {
            value = value.replace(new RegExp(`\\s*${attr}="[^"]*"`, 'g'), '');
        }

        return value;
    }
    removeUnusedTag(value) {
        //Xóa luôn theo cặp <clientScript>...</clientScript> 
        value = value.replace(/<clientScript>.*?<\/clientScript>\s*/g, '');
        value = value.replace(/<query>.*?<\/query>\s*/g, '');
        value = this.removeElement(value);
        return value
    }



    async filterDirField(paths) {
        var fields = await Promise.all(
            paths.map(path => {
                return this.getListField(path)
            })
        );

        fields = fields.filter(item => item != null && item.length > 0);
        return fields
    }

    async gridField(paths) {
        var fields = await Promise.all(
            paths.map(path => {
                return this.getListField(path)
            })
        );
        fields = fields.filter(item => item != null && item.length > 0);
        return fields
    }

}


class DatabaseRender {
    constructor() {
        this.paths = {
            database: path.resolve(__dirname, '..', 'Database'),
            db_autoComplete: path.resolve(__dirname, '..', 'Database', 'AutoComplete')
        }
        this.baseDir = this.createBasePath();
        this.dbMap = new Map(); // Lưu nhiều DB theo folder
    }

    deleteDatabase() {
        var db_folder = ['Filter', 'GridInput', 'GridView', 'Dir'];
        db_folder.forEach((folder) => {
            var folderPath = path.join(this.paths.database, folder);
            // Xóa thư mục (nếu tồn tại)
            if (fs.existsSync(folderPath)) {
                try {
                    fs.rmSync(folderPath, { recursive: true, force: true });
                }
                catch (ex) {
                    vscode.window.showErrorMessage(`Xin reload lại Vscode và thử lại.`);
                }
            }
        });
    }


    createBasePath() {
        var baseDir = this.paths.database;
        if (!fs.existsSync(baseDir)) {
            fs.mkdirSync(baseDir, { recursive: true });
        }
        return baseDir;
    }

    getDbForFolder(folder) {
        if (!this.dbMap.has(folder)) {
            var folderPath = path.join(this.baseDir, `${folder}`);
            var db = level(folderPath);
            this.dbMap.set(folder, db);
        }
        return this.dbMap.get(folder);
    }

    async insertData(val) {
        for (var folder_fields of val) {
            for (var [folder, fields] of folder_fields) {
                var db = this.getDbForFolder(folder);
                var batchOps = [fields].map(([field, value, controller]) => {
                    return {
                        type: 'put',
                        key: field,
                        value: value
                    }
                }
                );

                await db.batch(batchOps);
            }
        }
    }

    async closeAll() {
        for (var db of this.dbMap.values()) {
            await db.close();
        }
        this.dbMap.clear();
    }
    async saveToAutoCompleteJson() {
        const databaseDir = this.paths.database;
        const baseDirAutoComplete = this.paths.db_autoComplete;

        var folders = fs.readdirSync(databaseDir).filter(name => {
            const fullPath = path.join(databaseDir, name);
            return fs.statSync(fullPath).isDirectory();
        });

        folders = folders.filter(folder => ['Dir', 'GridInput', 'GridView', 'Filter'].includes(folder))

        folders.forEach(async (folder) => {
            var keys = await this.getAllKeys(folder);
            keys = keys.filter(key => !key.includes('&'))
            var arr = keys.map((key) => {
                return {
                    "label": key,
                    "detail": `${folder}`,
                    "insertText": `${key};`
                }
            })
            var path_json = path.join(baseDirAutoComplete, `${folder}.json`)
            fs.writeFileSync(path_json, JSON.stringify(arr, null, 2), 'utf8');
        })
    }
    async run(val) {
        await this.insertData(val);
        await this.closeAll();
    }

    async getAllKeys(folder) {
        const db = this.getDbForFolder(folder);
        const keys = [];
        try {
            await new Promise((resolve, reject) => {
                db.createReadStream()
                    .on('data', (data) => {
                        keys.push(data.key);
                    })
                    .on('end', resolve)
                    .on('error', reject);
            });

            return keys;

        } finally {
            await db.close(); // Luôn đóng DB dù thành công hay lỗi
            this.dbMap.clear();
        }
    }

    async getValueForKey(folder, key) {
        const db = this.getDbForFolder(folder);
        try {
            const value = await new Promise((resolve, reject) => {
                db.get(key, (err, value) => {
                    if (err) {
                        if (err.notFound) {
                            resolve(null);  // Key không tồn tại
                        } else {
                            reject(err);    // Lỗi khác
                        }
                    } else {
                        resolve(value);
                    }
                });
            });
            return value;
        } finally {
            await db.close(); // Đóng DB sau khi đọc xong, kể cả khi có lỗi
        }
    }

}
module.exports = RenderXMLToDB;
