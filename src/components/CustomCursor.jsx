// import React, { useEffect, useState } from "react";
// import { motion } from "framer-motion";

// const CustomCursor = () => {
//   const [pos, setPos] = useState({ x: 0, y: 0 });
//   const [click, setClick] = useState(false);

//   useEffect(() => {
//     const move = (e) => {
//       setPos({ x: e.clientX, y: e.clientY });
//     };

//     const down = () => setClick(true);
//     const up = () => setClick(false);

//     window.addEventListener("mousemove", move);
//     window.addEventListener("mousedown", down);
//     window.addEventListener("mouseup", up);

//     return () => {
//       window.removeEventListener("mousemove", move);
//       window.removeEventListener("mousedown", down);
//       window.removeEventListener("mouseup", up);
//     };
//   }, []);

//   return (
//     <motion.div
//       className="fixed top-0 left-0 pointer-events-none z-[9999]"
//       animate={{
//         x: pos.x - 16,
//         y: pos.y - 16,
//         scale: click ? 0.75 : 1,
//       }}
//       transition={{
//         type: "spring",
//         stiffness: 500,
//         damping: 30,
//         mass: 0.5,
//       }}
//     >
//       <img
//         src="/cursor.png"
//         alt="cursor"
//         className="w-8 h-8 select-none"
//         draggable={false}
//       />
//     </motion.div>
//   );
// };

// export default CustomCursor;