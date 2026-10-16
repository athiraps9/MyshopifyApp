// Shopify uses cursor paging: we only know "next" and "previous" tokens.
export default function Pagination({ page, onChange }) {
  if (!page || (!page.next_page_info && !page.previous_page_info)) return null;
  return (
    <div className="pager">
      <button disabled={!page.previous_page_info} onClick={() => onChange(page.previous_page_info)}>
        Previous
      </button>
      <button disabled={!page.next_page_info} onClick={() => onChange(page.next_page_info)}>
        Next
      </button>
    </div>
  );
}
