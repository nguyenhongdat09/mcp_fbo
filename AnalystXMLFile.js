const vscode = require('vscode');
const fs = require('fs');

class AnalystXMLFile {
    async getListField(filePath = '', content = '') {
        try {
            if (content === '') 
                content = await fs.promises.readFile(filePath, 'utf8');
    
            const fieldsRegex = /<fields>([\s\S]*?)<\/fields>/g;
            const fieldsMatches = content.match(fieldsRegex);
            if (!fieldsMatches) {
                console.error('No fields found');
                return;
            }
            var xmlFields = fieldsMatches[0];
            const fieldRegex = /<field[^>]*name="([^"]+)"[^>]*>[\s\S]*?<\/field>/g;
            const result = [];
            let match;
            while ((match = fieldRegex.exec(xmlFields)) !== null) {
                var key_t = match[1];
                var value_t = match[0];
              
                result.push({ key: key_t, value: value_t });
            }
            return result;
            
        } catch (error) {
            vscode.window.showErrorMessage(`Error parsing XML: ${error} at ${filePath}`);
            return [];
        } 
    }
    
    createCompleteItem(text, line, position) {
        const completionItem = new vscode.InlineCompletionItem(text.trim());
        completionItem.command = {
            command: 'fbo-autocomplete.applyCompletionItem',
            title: 'zlkqlksk',
            arguments: [line, position]
        };
        completionItem.range = new vscode.Range(position, position); // Đảm bảo chỉ thay đổi từ vị trí hiện tại
        return completionItem;
    }
    async getListViewOnGrid(filePath = '', content = '') {
        try {
            if (content === '') 
                content = await fs.promises.readFile(filePath, 'utf8');

            const fieldsRegex = /<views>([\s\S]*?)<\/views>/g;
            const fieldsMatches = content.match(fieldsRegex);
            if (!fieldsMatches) {
                console.error('No fields found');
                return;
            }
            var xmlFields = fieldsMatches[0];
            const fieldRegex = /<field[^>]*name="([^"]+)"[^>]*\/?>/g;
            const result = [];
            let match;
            while ((match = fieldRegex.exec(xmlFields)) !== null) {
                var key_t = match[1]
                var value_t = match[0];
                result.push({key: key_t, value: value_t});
            }
            return result;
            
        }
        catch (error) {
            vscode.window.showErrorMessage(`Error parsing XML: ${error} at ${filePath}`);
            return [];
        } 
    }

}
module.exports = AnalystXMLFile;