import path from "path";

// Check file type
export const checkFileType = file => {
  const filetypes = /jpeg|jpg|png|gif/;
  const extname = filetypes.test(path.extname(file.originalname).toLowerCase());
  const mimetype = filetypes.test(file.mimetype);

  if (mimetype && extname) {
    // return cb(null, true);
    return { isValid: true, error: null };
  } else {
    // cb("Error: Images only! (jpeg, jpg, png, gif)");
    return { isValid: false, error: "Error: Images only! (jpeg, jpg, png, gif)" };
  }
};
