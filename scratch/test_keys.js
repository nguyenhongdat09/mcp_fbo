const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { decryptFContent, decryptBlock } = require('e:\\CustomizeExtension\\fbo-autocomplete\\src\\TreeFile\\ConvertXml\\FboEncryptedDecryptor.js');

const fPath = "z:\\FBO\\VLOTUS\\SP228\\App_Data\\Controllers\\Filter\\AccountBalanceAdjustment.f";
const fContent = fs.readFileSync(fPath, 'utf8');

const testCandidates = [
    { name: "extensionKey as utf8 key (zero iv)", key: "f3c0c32cfzIm4NXk", iv: Buffer.alloc(16, 0) },
    { name: "extensionKey as password (md5)", password: "f3c0c32cfzIm4NXk" },
    { name: "licenseKey as password", password: "FBO-5BD26C4329E00B9165E17E16-30" },
    { name: "FastBusiness as password", password: "FastBusiness" },
    { name: "Fast as password", password: "Fast" },
    { name: "fast as password", password: "fast" },
    { name: "VLOTUS as password", password: "VLOTUS" },
    { name: "SP228 as password", password: "SP228" },
];

for (const cand of testCandidates) {
    console.log(`Testing: ${cand.name}...`);
    try {
        const res = decryptFContent(fContent, cand);
        if (res.decryptedCount > 0) {
            console.log(`SUCCESS! Decrypted ${res.decryptedCount} blocks!`);
            console.log(res.content.slice(0, 500));
            process.exit(0);
        } else {
            console.log(`Failed: ${res.failed[0]?.error}`);
        }
    } catch (e) {
        console.log(`Error: ${e.message}`);
    }
}
