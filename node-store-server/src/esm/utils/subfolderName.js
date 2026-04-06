"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.subfolderName = void 0;
const dayjs_1 = __importDefault(require("dayjs"));
const subfolderName = () => {
    const dateStr = (0, dayjs_1.default)().format("YYYY[/]MM");
    return dateStr;
};
exports.subfolderName = subfolderName;
