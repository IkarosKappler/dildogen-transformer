"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.checkFileType = void 0;
var path_1 = __importDefault(require("path"));
// Check file type
var checkFileType = function (file) {
    var filetypes = /jpeg|jpg|png|gif/;
    var extname = filetypes.test(path_1.default.extname(file.originalname).toLowerCase());
    var mimetype = filetypes.test(file.mimetype);
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
