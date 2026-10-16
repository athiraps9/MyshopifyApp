import { useState } from "react";

export default function SearchBar({ placeholder = "Search...", onSearch }) {
  const [text, setText] = useState("");
  return (
    <form
      className="search"
      onSubmit={(e) => {
        e.preventDefault();
        onSearch(text.trim());
      }}
    >
      <input value={text} placeholder={placeholder} onChange={(e) => setText(e.target.value)} />
      <button type="submit">Search</button>
    </form>
  );
}
