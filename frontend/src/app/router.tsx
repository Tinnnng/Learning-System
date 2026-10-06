import { createBrowserRouter } from 'react-router'
import { Layout } from './Layout'
import { routes } from './registry'

export const router = createBrowserRouter([{ element: <Layout />, children: routes }])
