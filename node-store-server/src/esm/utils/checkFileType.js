"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.checkFileType = void 0;
const path_1 = __importDefault(require("path"));
// Check file type
const checkFileType = file => {
    const filetypes = /jpeg|jpg|png|gif/;
    const extname = filetypes.test(path_1.default.extname(file.originalname).toLowerCase());
    const mimetype = filetypes.test(file.mimetype);
    if (mimetype && extname) {
        // return cb(null, true);
        return { isValid: true, error: null };
    }
    else {
        // cb("Error: Images only! (jpeg, jpg, png, gif)");
        return { isValid: false, error: "Error: Images only! (jpeg, jpg, png, gif)" };
    }
};
exports.checkFileType = checkFileType;
