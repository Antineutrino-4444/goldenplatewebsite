import { useCallback, useEffect, useRef, useState } from 'react'
import {
  DndContext,
  DragOverlay,
  MouseSensor,
  TouchSensor,
  closestCenter,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import {
  SortableContext,
  arrayMove,
  rectSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical } from 'lucide-react'

// Default card order
const DEFAULT_CARD_ORDER = [
  'student-database',
  'teacher-database',
  'export-house-data',
  'draw-center',
]

// SortableCard wrapper component
function SortableCard({ id, children, minHeight }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    position: 'relative',
    minHeight: minHeight || undefined,
  }

  return (
    <div ref={setNodeRef} style={style} className="relative group h-full">
      <div
        {...attributes}
        {...listeners}
        className="absolute top-3 right-3 z-10 p-1.5 rounded-md bg-gray-100/80 hover:bg-gray-200 cursor-grab active:cursor-grabbing opacity-0 group-hover:opacity-100 transition-opacity shadow-sm"
        title="Drag to reorder"
      >
        <GripVertical className="h-4 w-4 text-gray-500" />
      </div>
      <div className="h-full">{children}</div>
    </div>
  )
}

// Card overlay shown while dragging
function CardOverlay({ children }) {
  return (
    <div className="opacity-90 shadow-2xl rounded-lg bg-white">
      {children}
    </div>
  )
}

export default function DraggableCardGrid({
  cards,
  cardOrder,
  onOrderChange,
  className = '',
  columns = 2,
}) {
  const [activeId, setActiveId] = useState(null)
  const [rowHeights, setRowHeights] = useState({})
  const gridRef = useRef(null)

  // Filter cardOrder to only include cards that exist
  const validOrder = cardOrder.filter(id => cards[id])

  // Calculate row assignments for 2-column layout
  const getRowForIndex = (index) => Math.floor(index / columns)

  const sensors = useSensors(
    useSensor(MouseSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(TouchSensor, {
      activationConstraint: {
        delay: 200,
        tolerance: 8,
      },
    })
  )

  const handleDragStart = (event) => {
    setActiveId(event.active.id)
  }

  const handleDragEnd = (event) => {
    const { active, over } = event
    setActiveId(null)

    if (over && active.id !== over.id) {
      const oldIndex = validOrder.indexOf(active.id)
      const newIndex = validOrder.indexOf(over.id)
      const newOrder = arrayMove(validOrder, oldIndex, newIndex)
      onOrderChange(newOrder)
    }
  }

  const handleDragCancel = () => {
    setActiveId(null)
  }

  // Measure and equalize row heights
  useEffect(() => {
    const measureHeights = () => {
      if (!gridRef.current) return

      const heights = {}
      const rowMaxHeights = {}

      // Measure each card
      validOrder.forEach((cardId, index) => {
        const element = gridRef.current.querySelector(`[data-card-id="${cardId}"]`)
        if (element) {
          const height = element.scrollHeight
          const row = getRowForIndex(index)
          if (!rowMaxHeights[row] || height > rowMaxHeights[row]) {
            rowMaxHeights[row] = height
          }
        }
      })

      // Assign max height to each card in the row
      validOrder.forEach((cardId, index) => {
        const row = getRowForIndex(index)
        heights[cardId] = rowMaxHeights[row]
      })

      setRowHeights(heights)
    }

    // Measure after render and on resize
    const timeoutId = setTimeout(measureHeights, 100)
    const resizeObserver = new ResizeObserver(measureHeights)

    if (gridRef.current) {
      resizeObserver.observe(gridRef.current)
    }

    return () => {
      clearTimeout(timeoutId)
      resizeObserver.disconnect()
    }
  }, [validOrder, columns])

  const activeCard = activeId ? cards[activeId] : null

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <SortableContext items={validOrder} strategy={rectSortingStrategy}>
        <div
          ref={gridRef}
          className={`grid grid-cols-1 gap-8 lg:grid-cols-${columns} ${className}`}
          style={{
            display: 'grid',
            gridTemplateColumns: `repeat(1, minmax(0, 1fr))`,
          }}
        >
          <style>{`
            @media (min-width: 1024px) {
              [data-draggable-grid] {
                grid-template-columns: repeat(${columns}, minmax(0, 1fr)) !important;
              }
            }
          `}</style>
          <div
            data-draggable-grid
            className="contents lg:grid lg:gap-8"
            style={{
              display: 'contents',
            }}
          >
            {validOrder.map((cardId, index) => {
              const cardContent = cards[cardId]
              if (!cardContent) return null

              return (
                <SortableCard
                  key={cardId}
                  id={cardId}
                  minHeight={rowHeights[cardId]}
                >
                  <div data-card-id={cardId} className="h-full">
                    {cardContent}
                  </div>
                </SortableCard>
              )
            })}
          </div>
        </div>
      </SortableContext>

      <DragOverlay>
        {activeCard ? <CardOverlay>{activeCard}</CardOverlay> : null}
      </DragOverlay>
    </DndContext>
  )
}

export { DEFAULT_CARD_ORDER }
