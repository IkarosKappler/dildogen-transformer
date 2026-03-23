import express from "express";
import bodyParser from "body-parser";
import multer from "multer";
import mime from "mime-types";
import os from "node:os";
import dayjs from "dayjs";
import cors from "cors";

import { fileURLToPath } from "node:url";
import { checkFileType } from "./utils/checkFileType";
import { uniqueId } from "./utils/uniqueId";
import fs from "fs";
import { WithCustomData } from "interfaces";
import { tryParseJSONString } from "./utils/tryParseJSONString";
import { subfolderName } from "./utils/subfolderName";
// import { hasRequiredFields } from "./utils/hasRequiedFields";

// const __dirname = fileURLToPath(new URL(".", import.meta.url));
// console.log("Starting dev server on ", __dirname);

const getStoragepath = (subfolderName: string): string => {
  return `./uploads/${subfolderName}/`;
};

const storeBase64EncodedFile = (req, fieldName: string, base64string: string, fileExtension: string) => {
  const subfolderName = (req as any as WithCustomData).customData.subfolder;
  // cb(null, "./uploads/");
  const storagePath = getStoragepath(subfolderName);
  fs.mkdirSync(storagePath, { recursive: true });
  // console.log("Getting file name ", file.fieldname);
  const uniquePrefix = (req as any as WithCustomData).customData.id;
  // console.log("MIME-Type", file.mimetype);
  const mimeType = "image/png";
  // const extension = mime.extension(file.mimetype);
  // console.log("extension", extension);
  const filename = `${uniquePrefix}-${fieldName}${fileExtension}`;
  const path = `${storagePath}${filename}`;
  // Drop the 'data:image/png;'
  // const B64_PREFIX = "data:image/png;";
  // const base64string_clean = base64string.substring(B64_PREFIX.length);
  // const buf = Buffer.from(base64string_clean, "base64");
  // fs.writeFileSync(path, buf.toString("binary"));
  var base64string_clean = base64string.replace(/^data:image\/png;base64,/, "");
  // require("fs").writeFile(path, base64string_clean, "base64", function (err) {
  //   console.log(err);
  // });
  fs.writeFileSync(path, base64string_clean, "base64");
  return { path: path, storagePath: storagePath, filename: filename };
};

async function createServer() {
  const app = express();
  const port = 1337;

  // HTML templates/views are located in the /views/ directory.
  app.set("view engine", "ejs");

  // app.use(bodyParser());
  app.use(bodyParser.urlencoded());
  app.use(bodyParser.json({ limit: "2mb" }));
  // app.use(bodyParser.text({ limit: "200mb" }));

  // Disabled CORS (attention! this is very unsafe!)
  app.use(
    cors({
      "allowedHeaders": ["Content-Type"],
      "origin": "*", // "https://127.0.0.1:8080",
      "preflightContinue": true
    })
  );

  const storage = multer.diskStorage({
    destination: function (req, file, cb) {
      const subfolderName = (req as any as WithCustomData).customData.subfolder;
      // cb(null, "./uploads/");
      const storagePath = getStoragepath(subfolderName);
      console.log("destination: ", storagePath);
      fs.mkdirSync(storagePath, { recursive: true });
      cb(null, storagePath);
    },
    filename: function (req, file, cb) {
      // const uniqueSuffix = Date.now() + "-" + Math.round(Math.random() * 1e9);
      console.log("Getting file name ", file.fieldname);
      const uniquePrefix = (req as any as WithCustomData).customData.id;
      console.log("MIME-Type", file.mimetype);
      const extension = mime.extension(file.mimetype);
      console.log("extension", extension);
      cb(null, `${uniquePrefix}-${file.fieldname}.${extension}`);
    }
  });

  const upload = multer({
    storage: storage,
    limits: { fileSize: 1000000 }, // 1MB file size limit
    fileFilter: function (req, file, cb) {
      console.log("File filter called.");
      // const fieldStatus = hasRequiredFields(req);
      // if (!fieldStatus.isValid) {
      //   cb(new Error(fieldStatus.error));
      //   return;
      // }
      // checkFileType(file, cb);
      const fileStatus = checkFileType(file);
      if (!fileStatus.isValid) {
        cb(new Error(fileStatus.error));
        return;
      }
      // Success
      cb(null, true);
    }
  });

  app.get("/index.html", async (req, res) => {
    // Since `appType` is `'custom'`, should serve response here.
    // Note: if `appType` is `'spa'` or `'mpa'`, Vite includes middlewares
    // to handle HTML requests and 404s so user middlewares should be added
    // before Vite's middlewares to take effect instead
    console.log("GET");
    const jsonResponse = { message: "OK" };
    console.log(jsonResponse);
    res.render("form");
  });

  app.post(
    "/model/put",
    // First step: create a unique ID for this request
    function (req, res, next) {
      if( !(req as any as WithCustomData).customData ) {
        (req as any as WithCustomData).customData = { id: uniqueId(), subfolder: subfolderName() };
      }
      // console.log("Created an ID for the request", req as any as WithCustomData);
      next();
    },
    // Note: _all_ sent fields (!) must be declared here. Otherwise an 'unexpected field' error is thrown.
    upload.fields([
      { name: "hidenfield" },
      { name: "modelName" },
      { name: "outlineSegmentCount" },
      { name: "shapeSegmentCount" },
      { name: "preview2d", maxCount: 1 }, // Not used, using b64 instead
      { name: "preview3d", maxCount: 1 }, // Not used, using b64 instead
      { name: "sculptmap", maxCount: 1 }, // Not used, using b64 instead
      { name: "preview2d_b64", maxCount: 1 },
      { name: "preview3d_b64", maxCount: 1 },
      { name: "sculptmap_b64", maxCount: 1 },
      { name: "bezierJSON" },
      { name: "bendAngle" }
    ]),
    function (req, res) {
      console.log("POST");
      // console.log(req.body);

      // Write JSON files and meta data
      const uniquePrefix = (req as any as WithCustomData).customData.id;
      const subfolderName = (req as any as WithCustomData).customData.subfolder;
      const storagePath = getStoragepath(subfolderName);
      fs.mkdirSync(storagePath, { recursive: true });

      const modelName = req.body["modelName"];
      const outlineSegmentCount = req.body["outlineSegmentCount"];
      const shapeSegmentCount = req.body["shapeSegmentCount"];
      const bezierJsonRaw = req.body["bezierJSON"];
      const bendAngleRaw = req.body["bendAngle"];
      const bendAngle = Number(bendAngleRaw);
      const bezierData = tryParseJSONString(bezierJsonRaw, null);
      const preview2d_b64 = req.body["preview2d_b64"];
      const preview3d_b64 = req.body["preview3d_b64"];
      const sculptmap_b64 = req.body["sculptmap_b64"];

      if (!modelName) {
        return res.status(400).send({ success: false, message: "Param 'modelName' is missing." });
      }
      if (!outlineSegmentCount) {
        return res.status(400).send({ success: false, message: "Param 'outlineSegmentCount' is missing." });
      }
      if (!shapeSegmentCount) {
        return res.status(400).send({ success: false, message: "Param 'shapeSegmentCount' is missing." });
      }
      if (!bezierJsonRaw) {
        return res.status(400).send({ success: false, message: "Param 'bezierJsonRaw' is missing." });
      }
      if (!bendAngleRaw) {
        return res.status(400).send({ success: false, message: "Param 'bendAngleRaw' is missing." });
      }
      if (!bendAngle) {
        return res.status(400).send({ success: false, message: "Param 'bendAngle' is missing." });
      }
      if (!bezierData) {
        return res.status(400).send({ success: false, message: "Param 'bezierData' is missing." });
      }
      if (!preview2d_b64) {
        return res.status(400).send({ success: false, message: "Param 'preview2d_b64' is missing." });
      }
      if (!preview3d_b64) {
        return res.status(400).send({ success: false, message: "Param 'preview3d_b64' is missing." });
      }
      if (!sculptmap_b64) {
        return res.status(400).send({ success: false, message: "Param 'sculptmap_b64' is missing." });
      }

      const filepath_preview2d = storeBase64EncodedFile(req, "preview2d_b64", preview2d_b64, ".png");
      const filepath_preview3d = storeBase64EncodedFile(req, "preview3d_b64", preview3d_b64, ".png");
      const filepath_sculptmap = storeBase64EncodedFile(req, "sculptmap_b64", sculptmap_b64, ".png");

      fs.writeFileSync(
        `./${storagePath}${uniquePrefix}-meta.json`,
        JSON.stringify(
          {
            date: dayjs().format(), // ISO data
            remoteIp: req.ip,
            version: "0.0.2",
            name: modelName,
            outlineSegmentCount: outlineSegmentCount,
            shapeSegmentCount: shapeSegmentCount,
            filepath_preview2d: filepath_preview2d.filename,
            filepath_preview3d: filepath_preview3d.filename,
            filepath_sculptmap: filepath_sculptmap.filename,
            bezierData: bezierData,
            bezierDataRaw: bezierJsonRaw,
            bendAngle: bendAngle,
            bendAngleRaw: bendAngleRaw
          },
          null,
          2
        )
      );

      const jsonResponse = { message: "OK" };
      console.log(jsonResponse);
      res.json(jsonResponse);
    }
  );

  await app.listen(port, () => {
    console.log(`Example app listening on port ${port}`);
  });
}

createServer();
