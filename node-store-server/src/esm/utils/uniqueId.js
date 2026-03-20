"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.uniqueId = void 0;
var dayjs_1 = __importDefault(require("dayjs"));
var uniqueId = function () {
    var dateStr = (0, dayjs_1.default)().format("YYYYMMDD-HHmmss");
    var randomStr = "".concat(Math.floor(Math.random() * 65535));
    return dateStr + "-" + randomStr;
};
exports.uniqueId = uniqueId;
