interface Props {
  page: number
  pages: number
  total: number
  onPage: (p: number) => void
}

export default function Pagination({ page, pages, total, onPage }: Props) {
  if (pages <= 1) return null
  return (
    <div className="flex items-center gap-2 mt-4 text-sm text-gray-600">
      <button
        disabled={page <= 1}
        onClick={() => onPage(page - 1)}
        className="px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-100"
      >
        ←
      </button>
      <span>
        {page} / {pages}
      </span>
      <button
        disabled={page >= pages}
        onClick={() => onPage(page + 1)}
        className="px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-100"
      >
        →
      </button>
      <span className="text-gray-400">({total} записей)</span>
    </div>
  )
}
